from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

import migrate
from app.config import get_settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]


def recreate_database(base_url: str, name: str) -> str:
    """Drop+create database `name` on the same server; return its connection URL."""
    # guard: tests drop databases, never let a misconfigured URL point at a real one
    if not (name.endswith("_test") or name.endswith("_scratch")):
        raise RuntimeError(f"refusing to drop non-test database {name!r}")
    admin = make_conninfo(base_url, dbname="postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return make_conninfo(base_url, dbname=name)


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Fresh test database built from the real migrations."""
    base = get_settings().test_database_url
    name = conninfo_to_dict(base)["dbname"]
    url = recreate_database(base, name)
    migrate.apply_migrations(url)
    return url


AUTH_TABLES = (
    "apple_consumed_challenges",
    "otp_codes",
    "sessions",
    "devices",
    "auth_identities",
    "users",
)


@pytest.fixture
def committed_auth_db_url(test_db_url):
    """Test database for tests that commit through their own pool; auth tables are emptied after.

    Committed rows would otherwise leak into later tests that count users, sessions or codes.
    """
    yield test_db_url
    with psycopg.connect(test_db_url, autocommit=True) as conn:
        conn.execute(
            sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(map(sql.Identifier, AUTH_TABLES)))
        )


@pytest.fixture
def scratch_db_url() -> str:
    """Empty database for migration-runner tests."""
    return recreate_database(get_settings().test_database_url, "jol_migrate_scratch")


@pytest.fixture
async def conn(test_db_url):
    """Async connection; everything done through it is rolled back after the test."""
    async with await psycopg.AsyncConnection.connect(test_db_url, row_factory=dict_row) as c:
        async with c.transaction(force_rollback=True):
            yield c


class TransactionalDatabase:
    """Drop-in for app.db.Database that reuses one connection (nested = savepoints)."""

    def __init__(self, conn):
        self.conn = conn

    @asynccontextmanager
    async def transaction(self):
        async with self.conn.transaction():
            yield self.conn


@pytest.fixture
async def client(conn):
    app = create_app()
    app.state.db = TransactionalDatabase(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
