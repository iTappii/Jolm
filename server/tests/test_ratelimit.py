"""Ш-51: rate limits shared through PostgreSQL (several API processes, one limit)."""

import asyncio
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app import worker
from app.db import Database, fetch_one
from app.main import create_app
from app.ratelimit import RateRule, acquire, acquire_own, cleanup_expired

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


async def test_window_slides_and_retry_after_counts_down(conn):
    rule = RateRule("t_slide", 2, 10)
    assert await acquire(conn, [(rule, "k")], now=T0) is None
    assert await acquire(conn, [(rule, "k")], now=T0 + timedelta(seconds=1)) is None
    assert (
        await acquire(conn, [(rule, "k")], now=T0 + timedelta(seconds=2)) == 9
    )  # oldest + 10 - 2 -> 8s, +1
    assert await acquire(conn, [(rule, "k")], now=T0 + timedelta(seconds=9.5)) == 1
    # the oldest hit left the window: one slot is free again
    assert await acquire(conn, [(rule, "k")], now=T0 + timedelta(seconds=10.5)) is None
    assert await acquire(conn, [(rule, "k")], now=T0 + timedelta(seconds=10.6)) is not None


async def test_keys_and_rules_are_independent(conn):
    a, b = RateRule("t_a", 1, 60), RateRule("t_b", 1, 60)
    assert await acquire(conn, [(a, "x")], now=T0) is None
    assert await acquire(conn, [(a, "y")], now=T0) is None
    assert await acquire(conn, [(b, "x")], now=T0) is None
    assert await acquire(conn, [(a, "x")], now=T0) is not None


async def test_a_refused_request_counts_nothing_anywhere(conn):
    install, ip = RateRule("t_install", 1, 60), RateRule("t_ip", 5, 60)
    assert await acquire(conn, [(install, "i"), (ip, "p")], now=T0) is None
    assert await acquire(conn, [(install, "i"), (ip, "p")], now=T0) is not None  # install full
    row = await fetch_one(conn, "SELECT count(*) AS n FROM rate_limit_hits")
    assert row["n"] == 2  # only the first request's two hits; the refusal added none


async def test_empty_rule_never_allows(conn):
    assert await acquire(conn, [(RateRule("t_zero", 0, 30), "k")], now=T0) == 30


async def test_no_raw_subject_is_stored(conn):
    await acquire(conn, [(RateRule("t_pii", 5, 60), "ip:203.0.113.7")], now=T0)
    row = await fetch_one(conn, "SELECT string_agg(key_hash, ',') AS k FROM rate_limit_hits")
    assert "203.0.113" not in row["k"] and len(row["k"]) == 64


async def test_cleanup_removes_only_expired_rows(conn):
    rule = RateRule("t_clean", 5, 10)
    await acquire(conn, [(rule, "k")], now=T0)
    await acquire(conn, [(rule, "k")], now=T0 + timedelta(seconds=30))
    assert await cleanup_expired(conn, now=T0 + timedelta(seconds=35)) == 1
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM rate_limit_hits"))["n"] == 1


async def test_retention_job_runs_the_cleanup(conn):
    await acquire(conn, [(RateRule("t_job", 5, 1), "k")], now=T0)  # long expired
    await worker._retention_cleanup(conn, {})
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM rate_limit_hits"))["n"] == 0


@pytest.fixture
async def two_pools(test_db_url):
    """Two independent connection pools on one committed database = two API processes."""
    first, second = Database(test_db_url, 1, 4), Database(test_db_url, 1, 4)
    await first.open()
    await second.open()
    yield first, second
    await first.close()
    await second.close()
    with psycopg.connect(test_db_url, autocommit=True) as c:
        c.execute("DELETE FROM rate_limit_hits")


async def test_concurrent_processes_share_one_limit(two_pools):
    rule = RateRule("t_shared", 5, 60)

    async def hit(db):
        return await acquire_own(db, [(rule, "same-key")])

    results = await asyncio.gather(*[hit(two_pools[i % 2]) for i in range(30)])
    assert sum(r is None for r in results) == 5  # limit x processes would have been 10
    assert all(r is not None and r >= 1 for r in results if r is not None)


async def test_overlapping_multi_key_requests_do_not_deadlock(two_pools):
    a, b = RateRule("t_dl_a", 100, 60), RateRule("t_dl_b", 100, 60)

    async def forward(db):
        return await acquire_own(db, [(a, "k"), (b, "k")])

    async def backward(db):
        return await acquire_own(db, [(b, "k"), (a, "k")])

    jobs = [forward(two_pools[0]) if i % 2 else backward(two_pools[1]) for i in range(40)]
    results = await asyncio.wait_for(asyncio.gather(*jobs), timeout=30)
    assert results == [None] * 40


async def test_two_app_instances_share_the_endpoint_limit(two_pools):
    apps = []
    for db in two_pools:
        app = create_app()
        app.state.db = db
        app.state.geocode_limiter.limit = 3
        apps.append(app)
    params = {"lat": 43.25, "lon": 76.95}
    codes = []
    for i in range(8):
        transport = ASGITransport(app=apps[i % 2], client=("198.51.100.77", 1000))
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/v1/geocode/reverse", params=params)
        codes.append(r.status_code)
        if r.status_code == 429:
            assert int(r.headers["Retry-After"]) >= 1
    assert codes.count(200) == 3 and codes.count(429) == 5


async def test_a_committed_count_survives_a_failing_request(two_pools):
    rule = RateRule("t_keep", 1, 60)
    assert await acquire_own(two_pools[0], [(rule, "k")]) is None
    assert await acquire_own(two_pools[1], [(rule, "k")]) is not None
