"""Job queue worker: Postgres `jobs` table + FOR UPDATE SKIP LOCKED (TECH_PLAN Ш-06).

Leasing (review Ш-01-03-06 №2-4, done before Ш-40):
- A claim is a short transaction of its own: due jobs get `locked_at` (the lease and the owner
  token) and `attempts + 1`, then it commits. Other workers skip leased jobs. A worker that dies
  mid-job leaves a lease that expires after `lease_sec`; the job is then claimed again and,
  because the attempt was counted at claim, a job that keeps killing its worker ends up dead
  instead of looping forever. A lease is not renewed: a handler must finish within it
  (`LEASE_SEC`, 5 minutes; external calls have their own timeouts).
- Completion (done / retry / dead) only applies while the lease is still ours (`locked_at` token).
- Two kinds of handlers:
  * DB handlers (default), `(conn, payload)`: run in ONE transaction with the done-mark, so their
    writes and the completion are atomic (exactly once for database effects). If the lease was
    lost meanwhile, the transaction is rolled back.
  * External handlers, `@register(kind, external=True)`, `(db, payload)`: no transaction is held
    by the worker while they call the outside world; they open short transactions themselves.
    Delivery is at-least-once: a crash after the effect repeats it, so they must be idempotent
    (pushes are: `push_notifications.sent_at`).
- The payload is wiped when a job ends (done or dead): it may hold secrets (the encrypted Apple
  token of `apple.revoke`). A job waiting for a retry keeps it.
"""

import asyncio
import logging
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.auth import apple_grants
from app.config import get_settings
from app.db import Database, execute, fetch_all, fetch_one
from app.jobs import sql
from app.logging_setup import setup_logging

log = logging.getLogger("app.worker")

Handler = Callable[[AsyncConnection, dict], Awaitable[None]]
_HANDLERS: Dict[str, Handler] = {}

BACKOFF_BASE_SEC = 30
BACKOFF_MAX_SEC = 3600
LEASE_SEC = 300


class LeaseLost(Exception):
    """The job's lease expired and another worker took it; this run's result is discarded."""


def register(kind: str, external: bool = False) -> Callable[[Handler], Handler]:
    """Decorator: register an async handler for a job kind.

    `(conn, payload)` runs inside the worker's transaction (database effects only); with
    `external=True` the handler is `(db, payload)` and manages its own short transactions.
    """

    def deco(fn: Handler) -> Handler:
        fn.external = external  # type: ignore[attr-defined]
        _HANDLERS[kind] = fn
        return fn

    return deco


def backoff_seconds(attempts: int) -> float:
    """Delay before the next try, given the number of attempts already made (>=1)."""
    return float(min(BACKOFF_BASE_SEC * 2 ** max(attempts - 1, 0), BACKOFF_MAX_SEC))


async def enqueue(
    conn: AsyncConnection,
    kind: str,
    payload: Optional[dict] = None,
    run_at: Optional[datetime] = None,
    dedupe_key: Optional[str] = None,
) -> Optional[Any]:
    """Insert a job. With a dedupe_key a duplicate is ignored (returns None)."""
    row = await fetch_one(conn, sql.ENQUEUE, (kind, Jsonb(payload or {}), run_at, dedupe_key))
    return row["id"] if row else None


# --- periodic (cron-like) schedule -------------------------------------------------------


@dataclass(frozen=True)
class Schedule:
    kind: str
    interval_sec: int
    payload: Optional[dict] = None


# Add recurring jobs here (weather re-check, mountain morning messages, ... in later steps).
SCHEDULES: List[Schedule] = [
    Schedule("jobs.cleanup", interval_sec=86400),
    Schedule("weather.scan", interval_sec=3600),  # Ш-40: trips due for a forecast re-check
    Schedule("mountain.scan", interval_sec=900),  # Ш-40: mountain mornings (SSOT §7.2)
]


async def enqueue_due_schedules(
    conn: AsyncConnection,
    now: Optional[datetime] = None,
    schedules: Optional[List[Schedule]] = None,
) -> int:
    """Enqueue one job per schedule per time slot. Race-free across workers: the slot
    number is part of a unique dedupe_key, so only the first insert wins."""
    now = now or datetime.now(timezone.utc)
    count = 0
    for sch in SCHEDULES if schedules is None else schedules:
        slot = int(now.timestamp()) // sch.interval_sec
        run_at = datetime.fromtimestamp(slot * sch.interval_sec, tz=timezone.utc)
        job_id = await enqueue(
            conn, sch.kind, sch.payload, run_at=run_at, dedupe_key=f"sched:{sch.kind}:{slot}"
        )
        count += 1 if job_id else 0
    return count


@register("jobs.cleanup")
async def _cleanup_done_jobs(conn: AsyncConnection, payload: dict) -> None:
    await execute(conn, sql.CLEANUP_DONE, (int(payload.get("keep_days", 14)),))


@register("apple.revoke", external=True)
async def _apple_revoke(db: Database, payload: dict) -> None:
    """Revoke a deleted user's Sign in with Apple grant; failure raises, so the job retries."""
    token = apple_grants.decrypt_token(payload["token"])
    await apple_grants.get_apple_grants().revoke(token)


# --- processing --------------------------------------------------------------------------


async def _finish(db: Database, statement: str, params: tuple) -> bool:
    async with db.transaction() as conn:
        return await fetch_one(conn, statement, params) is not None


async def _run_job(db: Database, job: dict, max_attempts: int) -> None:
    kind, token = job["kind"], job["locked_at"]
    error: Optional[str] = None
    try:
        handler = _HANDLERS.get(kind)
        if handler is None:
            raise LookupError(f"no handler for kind {kind!r}")
        if getattr(handler, "external", False):
            await handler(db, job["payload"])
            if not await _finish(db, sql.MARK_DONE, (job["id"], token)):
                log.warning("lease lost after an external job ran", extra={"kind": kind})
        else:
            async with db.transaction() as conn:
                await handler(conn, job["payload"])
                if await fetch_one(conn, sql.MARK_DONE, (job["id"], token)) is None:
                    raise LeaseLost()  # rolls back the handler's writes
    except LeaseLost:
        log.warning("lease lost, result discarded", extra={"job_id": str(job["id"]), "kind": kind})
        return
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:2000]
        log.warning("job failed", extra={"job_id": str(job["id"]), "kind": kind, "err": error})
    if error is not None:
        if job["attempts"] >= max_attempts:  # the attempt was counted at claim
            await _finish(db, sql.MARK_DEAD, (error, job["id"], token))
        else:
            delay = backoff_seconds(job["attempts"])
            await _finish(db, sql.MARK_RETRY, (error, delay, job["id"], token))


async def process_batch(
    db: Database, batch_size: int = 5, max_attempts: int = 5, lease_sec: int = LEASE_SEC
) -> int:
    """Claim up to `batch_size` due jobs and run them one by one. Returns the number claimed."""
    async with db.transaction() as conn:
        await execute(conn, sql.REAP_EXHAUSTED, (lease_sec, max_attempts))
        jobs = await fetch_all(conn, sql.CLAIM, (lease_sec, batch_size))
    for job in jobs:
        await _run_job(db, job, max_attempts)
    return len(jobs)


async def run_worker(
    db: Database,
    stop: asyncio.Event,
    batch_size: int = 5,
    poll_interval: float = 2.0,
    max_attempts: int = 5,
    lease_sec: int = LEASE_SEC,
) -> None:
    last_schedule = 0.0
    while not stop.is_set():
        try:
            if time.monotonic() - last_schedule >= 10:  # slot dedupe makes this cheap and safe
                async with db.transaction() as conn:
                    await enqueue_due_schedules(conn)
                last_schedule = time.monotonic()
            n = await process_batch(db, batch_size, max_attempts, lease_sec)
        except Exception:
            log.exception("worker iteration failed")
            n = 0
        if n == 0:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
            except asyncio.TimeoutError:
                pass


async def _main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    db = Database(settings.database_url, 1, max(2, settings.db_pool_min))
    await db.open()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker started")
    try:
        await run_worker(
            db,
            stop,
            settings.worker_batch_size,
            settings.worker_poll_interval_sec,
            settings.worker_max_attempts,
            settings.worker_lease_sec,
        )
    finally:
        await db.close()
        log.info("worker stopped")


# Live-plan handlers (Ш-40) register themselves on import; this must stay the last import.
import app.live.jobs  # noqa: E402,F401

if __name__ == "__main__":
    # run the module's normal copy: `python -m app.worker` executes this file as `__main__`,
    # whose handler registry would be a different one from the one `app.live.jobs` fills
    from app.worker import _main as main

    asyncio.run(main())
