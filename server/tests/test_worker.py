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


# --- leasing (review Ш-01-03-06 №2-4) ------------------------------------------------------
async def one(db):
    async with db.transaction() as c:
        return await fetch_one(c, "SELECT * FROM jobs")


async def test_claim_counts_the_attempt_and_holds_a_lease(db):
    seen = []

    @worker.register("test.lease")
    async def handle(conn, payload):
        seen.append(1)

    async with db.transaction() as c:
        await worker.enqueue(c, "test.lease", {"secret": "x"})
        await execute(c, "UPDATE jobs SET locked_at = now()")  # a worker holds it right now
    assert await worker.process_batch(db) == 0 and seen == []  # leased: not taken
    async with db.transaction() as c:
        await execute(c, "UPDATE jobs SET locked_at = now() - interval '10 minutes'")
    assert await worker.process_batch(db) == 1 and seen == [1]  # lease expired: taken again
    job = await one(db)
    assert job["attempts"] == 1 and job["done_at"] is not None and job["locked_at"] is None


async def test_a_job_that_kills_its_worker_ends_dead_instead_of_looping(db):
    ran = []

    @worker.register("test.crash")
    async def handle(conn, payload):
        ran.append(1)

    async with db.transaction() as c:
        await worker.enqueue(c, "test.crash", {"token": "secret"})
        # the worker was killed during its 5th attempt, five minutes ago
        await execute(c, "UPDATE jobs SET attempts = 5, locked_at = now() - interval '10 minutes'")
    assert await worker.process_batch(db, max_attempts=5) == 0 and ran == []
    job = await one(db)
    assert job["done_at"] is not None and "lease expired" in job["error"]
    assert job["payload"] == {}


async def test_payload_is_wiped_when_a_job_ends_but_kept_for_a_retry(db):
    @worker.register("test.secret")
    async def handle(conn, payload):
        if payload.get("fail"):
            raise RuntimeError("no")

    async with db.transaction() as c:
        await worker.enqueue(c, "test.secret", {"token": "s3cret", "fail": True})
    assert await worker.process_batch(db, max_attempts=2) == 1
    job = await one(db)
    assert job["payload"]["token"] == "s3cret" and job["done_at"] is None  # retry needs it
    async with db.transaction() as c:
        await execute(c, "UPDATE jobs SET run_at = now()")
    assert await worker.process_batch(db, max_attempts=2) == 1
    job = await one(db)
    assert job["done_at"] is not None and job["payload"] == {}  # dead: wiped

    async with db.transaction() as c:
        await execute(c, "TRUNCATE jobs")
        await worker.enqueue(c, "test.secret", {"token": "s3cret"})
    await worker.process_batch(db)
    job = await one(db)
    assert job["done_at"] is not None and job["error"] is None and job["payload"] == {}


async def test_a_db_handler_loses_its_writes_when_the_lease_was_taken_over(db):
    @worker.register("test.slow")
    async def handle(conn, payload):
        await worker.enqueue(conn, "test.side_effect")
        async with db.transaction() as other:  # another worker's claim after the lease expired
            await execute(
                other, "UPDATE jobs SET locked_at = clock_timestamp() WHERE kind = 'test.slow'"
            )

    async with db.transaction() as c:
        await worker.enqueue(c, "test.slow")
    assert await worker.process_batch(db) == 1
    async with db.transaction() as c:
        kinds = [r["kind"] for r in await fetch_all(c, "SELECT kind FROM jobs")]
        slow = await fetch_one(c, "SELECT done_at FROM jobs WHERE kind = 'test.slow'")
    assert kinds == ["test.slow"]  # the side effect was rolled back
    assert slow["done_at"] is None  # not marked done by a worker that no longer owns it


async def test_an_external_handler_runs_without_a_transaction_held_on_its_job(db):
    @worker.register("test.external", external=True)
    async def handle(database, payload):
        async def touch():
            async with database.transaction() as c:  # would block if the worker held the row
                await execute(c, "UPDATE jobs SET error = 'seen' WHERE kind = 'test.external'")

        await asyncio.wait_for(touch(), timeout=5)

    async with db.transaction() as c:
        await worker.enqueue(c, "test.external", {"token": "t"})
    assert await worker.process_batch(db) == 1
    job = await one(db)
    assert job["done_at"] is not None and job["error"] is None and job["payload"] == {}


async def test_an_external_handler_failure_is_retried_with_its_payload(db):
    @worker.register("test.external_fail", external=True)
    async def handle(database, payload):
        raise RuntimeError("push gateway down")

    async with db.transaction() as c:
        await worker.enqueue(c, "test.external_fail", {"n": 1})
    assert await worker.process_batch(db) == 1
    job = await one(db)
    assert job["attempts"] == 1 and job["done_at"] is None and job["payload"] == {"n": 1}
    assert "gateway" in job["error"]
