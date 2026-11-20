"""Job queue worker: Postgres `jobs` table + FOR UPDATE SKIP LOCKED (TECH_PLAN Ш-06).

Exactly-once: a batch is claimed, handled and marked done inside ONE transaction. Concurrent
workers skip rows locked by others; a crashed worker's transaction rolls back and the job
is picked up again. Each job runs in a savepoint so one failure doesn't affect others
in the batch. Handlers get (conn, payload) and may write to the DB atomically with the
done-mark.
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

from app.config import get_settings
from app.db import Database, execute, fetch_all, fetch_one
from app.jobs import sql
from app.logging_setup import setup_logging

log = logging.getLogger("app.worker")

Handler = Callable[[AsyncConnection, dict], Awaitable[None]]
_HANDLERS: Dict[str, Handler] = {}

BACKOFF_BASE_SEC = 30
BACKOFF_MAX_SEC = 3600


def register(kind: str) -> Callable[[Handler], Handler]:
    """Decorator: register an async handler `(conn, payload) -> None` for a job kind."""

    def deco(fn: Handler) -> Handler:
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


# --- processing --------------------------------------------------------------------------


async def process_batch(db: Database, batch_size: int = 5, max_attempts: int = 5) -> int:
    """Claim up to `batch_size` due jobs and run them. Returns the number claimed."""
    async with db.transaction() as conn:
        jobs = await fetch_all(conn, sql.CLAIM, (batch_size,))
        for job in jobs:
            await execute(conn, sql.MARK_CLAIMED, (job["id"],))
            error: Optional[str] = None
            try:
                handler = _HANDLERS.get(job["kind"])
                if handler is None:
                    raise LookupError(f"no handler for kind {job['kind']!r}")
                async with conn.transaction():  # savepoint
                    await handler(conn, job["payload"])
                    await execute(conn, sql.MARK_DONE, (job["id"],))
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:2000]
                log.warning(
                    "job failed",
                    extra={"job_id": str(job["id"]), "kind": job["kind"], "err": error},
                )
            if error is not None:
                attempts = job["attempts"] + 1
                if attempts >= max_attempts:
                    await execute(conn, sql.MARK_DEAD, (error, job["id"]))
                else:
                    await execute(
                        conn, sql.MARK_RETRY, (error, backoff_seconds(attempts), job["id"])
                    )
        return len(jobs)


async def run_worker(
    db: Database,
    stop: asyncio.Event,
    batch_size: int = 5,
    poll_interval: float = 2.0,
    max_attempts: int = 5,
) -> None:
    last_schedule = 0.0
    while not stop.is_set():
        try:
            if time.monotonic() - last_schedule >= 10:  # slot dedupe makes this cheap and safe
                async with db.transaction() as conn:
                    await enqueue_due_schedules(conn)
                last_schedule = time.monotonic()
            n = await process_batch(db, batch_size, max_attempts)
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
        )
    finally:
        await db.close()
        log.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(_main())
