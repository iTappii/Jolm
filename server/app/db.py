"""PostgreSQL access: psycopg 3 async pool + thin helpers. Raw SQL only, always parameterized."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional, Sequence

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

Params = Optional[Sequence[Any]]


class Database:
    def __init__(self, conninfo: str, min_size: int = 1, max_size: int = 10) -> None:
        self.pool = AsyncConnectionPool(
            conninfo,
            min_size=min_size,
            max_size=max_size,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def open(self) -> None:
        # wait=False: the API must start (and /health report 503) even if the DB is down
        await self.pool.open(wait=False)

    async def close(self) -> None:
        await self.pool.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncConnection]:
        """Connection inside a transaction: commit on success, rollback on exception."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                yield conn


async def fetch_one(conn: AsyncConnection, query: str, params: Params = None) -> Optional[dict]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchone()


async def fetch_all(conn: AsyncConnection, query: str, params: Params = None) -> list:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def execute(conn: AsyncConnection, query: str, params: Params = None) -> int:
    """Run a statement, return affected row count."""
    async with conn.cursor() as cur:
        await cur.execute(query, params)
        return cur.rowcount
