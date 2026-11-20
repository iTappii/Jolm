import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app import worker
from app.db import Database, execute, fetch_all, fetch_one


@pytest.fixture
async def db(test_db_url):
    database = Database(test_db_url, 1, 6)
    await database.open()
    await database.pool.wait()
    async with database.transaction() as c:
        await execute(c, "TRUNCATE jobs")
    yield database
    async with database.transaction() as c:
        await execute(c, "TRUNCATE jobs")
    await database.close()


@pytest.fixture(autouse=True)
def clean_handlers():
    saved = dict(worker._HANDLERS)
    yield
    worker._HANDLERS.clear()
    worker._HANDLERS.update(saved)


async def test_each_job_runs_exactly_once_with_two_parallel_workers(db):
    executed = []

    @worker.register("test.count")
    async def handle(conn, payload):
        await asyncio.sleep(0.01)  # widen the race window
        executed.append(payload["n"])

    total = 40
    async with db.transaction() as c:
        for n in range(total):
            await worker.enqueue(c, "test.count", {"n": n})

    async def one_worker():
        while await worker.process_batch(db, batch_size=3):
            pass

    await asyncio.gather(one_worker(), one_worker())

    assert sorted(executed) == list(range(total))  # no loss, no duplicates
    async with db.transaction() as c:
        row = await fetch_one(c, "SELECT count(*) AS n FROM jobs WHERE done_at IS NOT NULL")
    assert row["n"] == total


async def test_failed_job_retries_with_backoff_then_dies(db):
    @worker.register("test.fail")
    async def handle(conn, payload):
        raise RuntimeError("boom")

    async with db.transaction() as c:
        await worker.enqueue(c, "test.fail")

    assert await worker.process_batch(db, max_attempts=2) == 1
    async with db.transaction() as c:
        job = await fetch_one(c, "SELECT * FROM jobs")
    assert job["attempts"] == 1 and job["done_at"] is None and "boom" in job["error"]
    assert job["run_at"] > datetime.now(timezone.utc) + timedelta(seconds=20)
    assert await worker.process_batch(db, max_attempts=2) == 0  # not due yet

    async with db.transaction() as c:
        await execute(c, "UPDATE jobs SET run_at = now()")
    assert await worker.process_batch(db, max_attempts=2) == 1
    async with db.transaction() as c:
        job = await fetch_one(c, "SELECT * FROM jobs")
    assert job["attempts"] == 2 and job["done_at"] is not None  # terminal failure


async def test_unknown_kind_is_a_failure_not_a_crash(db):
    async with db.transaction() as c:
        await worker.enqueue(c, "test.unknown")
    assert await worker.process_batch(db) == 1
    async with db.transaction() as c:
        job = await fetch_one(c, "SELECT error FROM jobs")
    assert "no handler" in job["error"]


async def test_one_failure_does_not_affect_others_in_batch(db):
    ok = []

    @worker.register("test.ok")
    async def good(conn, payload):
        ok.append(1)

    @worker.register("test.bad")
    async def bad(conn, payload):
        raise ValueError("x")

    async with db.transaction() as c:
        await worker.enqueue(c, "test.bad")
        await worker.enqueue(c, "test.ok")
    await worker.process_batch(db, batch_size=5)
    assert ok == [1]


async def test_schedule_enqueues_once_per_slot_even_when_called_twice(db):
    sched = [worker.Schedule("test.tick", interval_sec=3600)]
    now = datetime(2026, 11, 21, 10, 30, tzinfo=timezone.utc)
    async with db.transaction() as c:
        a = await worker.enqueue_due_schedules(c, now, sched)
        b = await worker.enqueue_due_schedules(c, now + timedelta(minutes=5), sched)
        nxt = await worker.enqueue_due_schedules(c, now + timedelta(hours=1), sched)
        rows = await fetch_all(c, "SELECT dedupe_key FROM jobs ORDER BY run_at")
    assert (a, b, nxt) == (1, 0, 1)
    assert len(rows) == 2
