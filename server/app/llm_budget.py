"""Daily model-token budgets (Ш-66): per registered user, per guest, and for the whole service.

Counters live in `llm_usage_daily` (migration 0035), one row per (day, hashed key); the day is the
default region's local day. `check` runs BEFORE the model is called (so a refused request costs
nothing); `record` adds the tokens a turn really used (`TurnRecord.usage`, input + output) after
it. One turn can therefore pass the line once. A limit of 0 means "no limit".

- Over the user's / guest's budget: 429 `llm_budget_exceeded` (+ Retry-After until the regional
  midnight). Over the global budget: 503 `llm_budget_service` (checked first).
- The global total crossing the warning percent and 100% is detected atomically in `record`
  (previous total below the line, new total at or above it), so it fires once per day across all
  API processes: a warning log and `jol_llm_budget_threshold_total{level=...}` in `/metrics`.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional

from psycopg import AsyncConnection

from app import metrics
from app.config import Settings
from app.db import execute, fetch_all, fetch_one
from app.errors import AppError
from app.regions import default_region

log = logging.getLogger(__name__)

GLOBAL = "global"
KEEP_DAYS = 3


@dataclass(frozen=True)
class Budget:
    """One counter: `scope:subject` hashed, with its daily limit (0 = unlimited)."""

    scope: str
    subject: str
    limit: int

    @property
    def key(self) -> str:
        return hashlib.sha256(("%s:%s" % (self.scope, self.subject)).encode()).hexdigest()


def budget_day(now: Optional[datetime] = None) -> date:
    """The current day in the default region (tests pass `now`)."""
    tz = default_region().tz
    return (now.astimezone(tz) if now else datetime.now(tz)).date()


def seconds_until_next_day(now: Optional[datetime] = None) -> int:
    tz = default_region().tz
    local = now.astimezone(tz) if now else datetime.now(tz)
    midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return max(1, int((midnight - local).total_seconds()) + 1)


def global_budget(settings: Settings) -> Budget:
    return Budget("global", GLOBAL, settings.llm_daily_tokens_global)


def user_budgets(settings: Settings, user_id) -> List[Budget]:
    return [
        global_budget(settings),
        Budget("user", str(user_id), settings.llm_daily_tokens_user),
    ]


def guest_budgets(settings: Settings, ip: str, install: Optional[str]) -> List[Budget]:
    budgets = [
        global_budget(settings),
        Budget("guest_ip", ip, settings.llm_daily_tokens_guest_ip),
    ]
    if install:
        budgets.append(Budget("guest_install", install, settings.llm_daily_tokens_guest_install))
    return budgets


_USED = "SELECT key_hash, tokens FROM llm_usage_daily WHERE day = %s AND key_hash = ANY(%s)"
_ADD = """
INSERT INTO llm_usage_daily (day, key_hash, tokens) VALUES (%(day)s, %(key)s, %(tokens)s)
ON CONFLICT (day, key_hash) DO UPDATE SET tokens = llm_usage_daily.tokens + EXCLUDED.tokens
RETURNING tokens
"""
_CLEANUP = "DELETE FROM llm_usage_daily WHERE day < %s"


async def check(
    conn: AsyncConnection, budgets: Iterable[Budget], now: Optional[datetime] = None
) -> None:
    """Raise 503 `llm_budget_service` / 429 `llm_budget_exceeded` if a budget is used up."""
    active = [b for b in budgets if b.limit > 0]
    if not active:
        return
    rows = await fetch_all(conn, _USED, (budget_day(now), [b.key for b in active]))
    used = {r["key_hash"]: r["tokens"] for r in rows}
    for budget in active:  # the global one comes first in the lists above
        if used.get(budget.key, 0) >= budget.limit:
            if budget.scope == GLOBAL:
                log.warning("llm global daily budget used up: refusing chat requests")
                raise AppError(
                    503,
                    "llm_budget_service",
                    headers={"Retry-After": str(seconds_until_next_day(now))},
                )
            raise AppError(
                429,
                "llm_budget_exceeded",
                headers={"Retry-After": str(seconds_until_next_day(now))},
            )


async def record(
    conn: AsyncConnection,
    budgets: Iterable[Budget],
    tokens: int,
    settings: Settings,
    now: Optional[datetime] = None,
) -> None:
    """Add a finished turn's tokens to every counter; watch the global total's thresholds."""
    if tokens <= 0:
        return
    day = budget_day(now)
    for budget in sorted(budgets, key=lambda b: b.key):  # fixed order: no deadlocks
        row = await fetch_one(conn, _ADD, {"day": day, "key": budget.key, "tokens": tokens})
        if budget.scope == GLOBAL:
            _watch_global(row["tokens"] - tokens, row["tokens"], budget.limit, settings)


def _watch_global(before: int, after: int, limit: int, settings: Settings) -> None:
    if limit <= 0:
        return
    for percent in sorted({settings.llm_budget_warn_percent, 100}):
        line = limit * percent / 100
        if before < line <= after:
            metrics.count_llm_budget_threshold(percent)
            log.warning(
                "llm global daily budget at %d%%: %d of %d tokens used", percent, after, limit
            )


async def global_used_today(conn: AsyncConnection, now: Optional[datetime] = None) -> int:
    key = Budget("global", GLOBAL, 0).key
    row = await fetch_one(
        conn,
        "SELECT tokens FROM llm_usage_daily WHERE day = %s AND key_hash = %s",
        (budget_day(now), key),
    )
    return row["tokens"] if row else 0


async def cleanup(conn: AsyncConnection, now: Optional[datetime] = None) -> int:
    return await execute(conn, _CLEANUP, (budget_day(now) - timedelta(days=KEEP_DAYS),))
