import psycopg.errors
import pytest
from psycopg.types.json import Jsonb

from app.db import execute, fetch_all, fetch_one
from app.jobs import sql


async def test_insert_and_select_job(conn):
    row = await fetch_one(conn, sql.ENQUEUE, ("demo", Jsonb({"a": 1}), None, None))
    assert row["id"]
    rows = await fetch_all(
        conn, "SELECT kind, payload, attempts FROM jobs WHERE id = %s", (row["id"],)
    )
    assert rows == [{"kind": "demo", "payload": {"a": 1}, "attempts": 0}]


async def test_dedupe_key_is_unique(conn):
    first = await fetch_one(conn, sql.ENQUEUE, ("demo", Jsonb({}), None, "k1"))
    second = await fetch_one(conn, sql.ENQUEUE, ("demo", Jsonb({}), None, "k1"))
    assert first is not None and second is None


async def test_postgis_available(conn):
    row = await fetch_one(conn, "SELECT ST_AsText(ST_MakePoint(%s, %s)) AS wkt", (76.9, 43.2))
    assert row["wkt"] == "POINT(76.9 43.2)"


async def test_parameters_are_not_interpolated(conn):
    evil = "x'; DROP TABLE jobs; --"
    await execute(conn, "INSERT INTO jobs (kind) VALUES (%s)", (evil,))
    row = await fetch_one(conn, "SELECT count(*) AS n FROM jobs WHERE kind = %s", (evil,))
    assert row["n"] == 1


async def test_failed_statement_raises(conn):
    with pytest.raises(psycopg.errors.UndefinedTable):
        await fetch_one(conn, "SELECT * FROM no_such_table")
