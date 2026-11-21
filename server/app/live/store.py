"""SQL of the live plan (Ш-40). Raw, parameterized (SSOT §14.1)."""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import execute, fetch_all, fetch_one

PROPOSAL_COLS = (
    "id, user_id, trip_id, reason, kind, status, trip_version, day, to_day, item_id, place_id, "
    "target_place_id, diff, created_at, decided_at"
)


async def pending(conn, trip_id: UUID) -> List[dict]:
    return await fetch_all(
        conn,
        "SELECT " + PROPOSAL_COLS + " FROM trip_change_proposals "
        "WHERE trip_id = %s AND status = 'pending'",
        (trip_id,),
    )


async def expire(conn, proposal_ids: List[UUID]) -> None:
    if proposal_ids:
        await execute(
            conn,
            "UPDATE trip_change_proposals SET status = 'expired', decided_at = now() "
            "WHERE id = ANY(%s) AND status = 'pending'",
            (proposal_ids,),
        )


async def expire_stale(conn, trip_id: UUID, version: int) -> None:
    await execute(
        conn,
        "UPDATE trip_change_proposals SET status = 'expired', decided_at = now() "
        "WHERE trip_id = %s AND status = 'pending' AND trip_version <> %s",
        (trip_id, version),
    )


async def already_proposed(conn, trip_id: UUID, place_id: UUID, day: date) -> bool:
    """A proposal (pending, accepted or declined) for this stop on this day exists: do not nag."""
    row = await fetch_one(
        conn,
        "SELECT 1 AS ok FROM trip_change_proposals WHERE trip_id = %s AND place_id = %s "
        "AND day = %s AND status <> 'expired' LIMIT 1",
        (trip_id, place_id, day),
    )
    return row is not None


async def insert_proposal(conn, spec: Dict[str, Any]) -> UUID:
    row = await fetch_one(
        conn,
        """
        INSERT INTO trip_change_proposals
            (user_id, trip_id, reason, kind, trip_version, day, to_day, item_id, place_id,
             target_place_id, diff)
        VALUES (%(user_id)s, %(trip_id)s, 'weather', %(kind)s, %(trip_version)s, %(day)s,
                %(to_day)s, %(item_id)s, %(place_id)s, %(target_place_id)s, %(diff)s)
        RETURNING id
        """,
        dict(spec, diff=Jsonb(spec["diff"])),
    )
    return row["id"]


async def add_chat_message(
    conn, chat_id: UUID, text: str, prompt_id: str, proposal_id: Optional[UUID] = None
) -> int:
    row = await fetch_one(
        conn,
        "INSERT INTO chat_messages (chat_id, role, content, prompt_id, finish, proposal_id) "
        "VALUES (%s, 'assistant', %s, %s, 'stop', %s) RETURNING id",
        (chat_id, text, prompt_id, proposal_id),
    )
    await execute(conn, "UPDATE chats SET updated_at = clock_timestamp() WHERE id = %s", (chat_id,))
    return row["id"]


async def add_notification(
    conn, user_id: UUID, kind: str, title: str, body: str, data: Dict[str, Any], dedupe_key: str
) -> Optional[UUID]:
    row = await fetch_one(
        conn,
        "INSERT INTO push_notifications (user_id, kind, title, body, data, dedupe_key) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (dedupe_key) DO NOTHING RETURNING id",
        (user_id, kind, title, body, Jsonb(data), dedupe_key),
    )
    return row["id"] if row else None


async def add_notice(conn, trip_id: UUID, day: date, kind: str) -> bool:
    row = await fetch_one(
        conn,
        "INSERT INTO trip_day_notices (trip_id, day, kind) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING RETURNING trip_id",
        (trip_id, day, kind),
    )
    return row is not None


async def chat_of(conn, chat_id: Optional[UUID]) -> Optional[dict]:
    if chat_id is None:
        return None
    return await fetch_one(conn, "SELECT id, locale FROM chats WHERE id = %s", (chat_id,))


async def proposals_of_trip(conn, trip_id: UUID, limit: int = 50) -> List[dict]:
    return await fetch_all(
        conn,
        "SELECT " + PROPOSAL_COLS + " FROM trip_change_proposals WHERE trip_id = %s "
        "ORDER BY created_at DESC, id LIMIT %s",
        (trip_id, limit),
    )


async def proposal_for_update(conn, user_id: UUID, proposal_id: UUID) -> Optional[dict]:
    """The user's proposal, its own row locked (foreign and missing look the same: None). The
    trip row is NOT locked here: accepting plans without it and locks it only to write (Ш-38 №1)."""
    return await fetch_one(
        conn,
        "SELECT " + PROPOSAL_COLS + " FROM trip_change_proposals "
        "WHERE id = %s AND user_id = %s FOR UPDATE",
        (proposal_id, user_id),
    )


async def set_status(conn, proposal_id: UUID, status: str) -> None:
    await execute(
        conn,
        "UPDATE trip_change_proposals SET status = %s, decided_at = now() WHERE id = %s",
        (status, proposal_id),
    )
