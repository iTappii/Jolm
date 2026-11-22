from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

import migrate
from app.config import get_settings
from app.main import create_app
from app.providers.storage.local import LocalStorage

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
    "analytics_events",  # Ш-50: events reference users (SET NULL) and trips
    "bookings",  # Ш-49: bookings hang off users and places
    "place_crowd_reports",  # Ш-47: check-ins and crowd reports hang off users
    "bonus_ledger",  # Ш-46: the bonus ledger hangs off users and submissions
    "submissions",  # Ш-44: user content hangs off users and places
    "uploads",
    "push_notifications",  # Ш-40: the push outbox, trip day notices and proposals hang off users
    "trip_day_notices",
    "trip_change_proposals",
    "user_memory_notes",  # Ш-41: LLM summaries hang off users
    "user_favorites",  # Ш-23b: favourites hang off users
    "user_place_signals",  # memory signals of trip edits (Ш-38) hang off users
    "trip_lodging_options",  # trips hang off users and chats (Ш-36)
    "trip_legs",
    "trip_items",
    "trips",
    "chat_live_alternatives",  # Ш-54: the live route hangs off chats
    "chat_live_stops",
    "chat_graph_nodes",  # chats hang off users, so TRUNCATE users needs them listed
    "chat_messages",
    "trip_briefs",
    "chats",
    "place_photos",  # author_user_id references users, so TRUNCATE users needs it listed
    "apple_consumed_challenges",
    "otp_codes",
    "session_retired_tokens",
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
    base = get_settings().test_database_url
    # named after the test DB, so two runs against different test DBs never drop each other's
    name = conninfo_to_dict(base)["dbname"].rsplit("_test", 1)[0] + "_migrate_scratch"
    return recreate_database(base, name)


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


@pytest.fixture
async def env(conn, tmp_path):
    """App + client + local storage for user-content tests (Ш-44)."""
    app = create_app()
    app.state.db = TransactionalDatabase(conn)
    app.state.storage = LocalStorage(tmp_path, "http://test", "k" * 32)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(app=app, client=client, storage=app.state.storage)


@pytest.fixture
async def chat_env(conn):
    """App + client for chat tests; set `env.app.state.llm_provider` to a scripted `FakeLLM`."""
    app = create_app()
    app.state.db = TransactionalDatabase(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield SimpleNamespace(app=app, client=c)


def parse_sse(text: str) -> list:
    """`[(event, data_dict), ...]` from a `text/event-stream` body; checks the framing."""
    import json

    events = []
    for block in text.split("\n\n"):
        if not block:
            continue
        lines = block.split("\n")
        assert len(lines) == 2 and lines[0].startswith("event: ") and lines[1].startswith("data: ")
        events.append((lines[0][len("event: ") :], json.loads(lines[1][len("data: ") :])))
    return events
