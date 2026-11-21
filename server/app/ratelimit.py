"""Rate limits shared by all API processes (Ш-51; before: in-process, review Ш-30 №1).

A `RateRule` is `(name, limit, window_sec)`. `acquire` counts one request against every
`(rule, subject)` pair in ONE transaction and counts nothing if any is full (a refused request
costs nothing). State lives in `rate_limit_hits` (migration 0025): sliding window, one row per
counted request, atomic across processes through a transaction-scoped advisory lock per key
(locks are taken in sorted order, so two requests with overlapping keys cannot deadlock).

- Pass the caller's `conn` when the count should commit/roll back with the caller's own
  transaction (registered chat); use `acquire_own(db, ...)` otherwise: it opens a short
  transaction of its own, so the count is kept even if the request later fails.
- Keys are hashed (sha256): no raw IP / install id / user id in the table.
- A database outage makes `acquire` raise; the request then fails, like any other DB request.
- Expired rows are removed by the worker (`retention.cleanup`, `cleanup_expired`).
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from psycopg import AsyncConnection

from app.db import execute, fetch_one


@dataclass
class RateRule:
    name: str
    limit: int
    window_sec: int


def key_hash(rule: RateRule, subject: str) -> str:
    return hashlib.sha256(("%s:%s" % (rule.name, subject)).encode()).hexdigest()


_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"

# The limit-th most recent live hit, if there are that many: the request is refused until it
# leaves the window. Seconds are rounded up (at least 1), like the former in-process limiter.
_BLOCKING_HIT = """
SELECT GREATEST(1, floor(extract(epoch FROM
           hit_at + make_interval(secs => %(window)s) - COALESCE(%(now)s, clock_timestamp())
       ))::int + 1) AS wait
FROM rate_limit_hits
WHERE key_hash = %(key)s
  AND hit_at > COALESCE(%(now)s, clock_timestamp()) - make_interval(secs => %(window)s)
ORDER BY hit_at DESC
OFFSET %(skip)s LIMIT 1
"""

_RECORD = """
INSERT INTO rate_limit_hits (key_hash, hit_at, expires_at)
VALUES (%(key)s, COALESCE(%(now)s, clock_timestamp()),
        COALESCE(%(now)s, clock_timestamp()) + make_interval(secs => %(window)s))
"""

_CLEANUP = "DELETE FROM rate_limit_hits WHERE expires_at < COALESCE(%s, clock_timestamp())"


async def acquire(
    conn: AsyncConnection,
    checks: Iterable[Tuple[RateRule, str]],
    now: Optional[datetime] = None,
) -> Optional[int]:
    """Count one request against every (rule, subject); nothing is counted if any is full.

    Returns None when allowed, else the Retry-After seconds. `now` is for tests only.
    """
    prepared: List[Tuple[RateRule, str]] = [(rule, key_hash(rule, s)) for rule, s in checks]
    for key in sorted({k for _, k in prepared}):
        await execute(conn, _LOCK, (key,))
    wait = 0
    for rule, key in prepared:
        row = await fetch_one(
            conn,
            _BLOCKING_HIT,
            {"key": key, "window": rule.window_sec, "now": now, "skip": max(rule.limit - 1, 0)},
        )
        if row is not None or rule.limit <= 0:
            wait = max(wait, row["wait"] if row else rule.window_sec)
    if wait:
        return wait
    for rule, key in prepared:
        await execute(conn, _RECORD, {"key": key, "window": rule.window_sec, "now": now})
    return None


async def acquire_own(db, checks: Iterable[Tuple[RateRule, str]]) -> Optional[int]:
    """`acquire` in a short transaction of its own (committed whatever the request does next)."""
    async with db.transaction() as conn:
        return await acquire(conn, checks)


async def cleanup_expired(conn: AsyncConnection, now: Optional[datetime] = None) -> int:
    return await execute(conn, _CLEANUP, (now,))
