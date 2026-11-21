"""SQL for registered-user chats (Ш-31). Raw, parameterized (SSOT §14.1)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from psycopg.types.json import Jsonb

from app.chat.brief import empty_brief, merge_filled_order
from app.db import execute, fetch_all, fetch_one

MAX_GRAPH_NODES = 30
CHAT_COLS = "id, title, locale, created_at, updated_at"


async def create_chat(conn, user_id: UUID, locale: str) -> Dict[str, Any]:
    row = await fetch_one(
        conn,
        "INSERT INTO chats (user_id, locale, created_at, updated_at) "
        "VALUES (%s, %s, clock_timestamp(), clock_timestamp()) RETURNING " + CHAT_COLS,
        (user_id, locale),
    )
    await execute(conn, "INSERT INTO trip_briefs (chat_id) VALUES (%s)", (row["id"],))
    return row


async def list_chats(conn, user_id: UUID, limit: int, before: Optional[datetime]) -> List[dict]:
    return await fetch_all(
        conn,
        """
        SELECT c.id, c.title, c.locale, c.created_at, c.updated_at,
               (SELECT m.content FROM chat_messages m
                WHERE m.chat_id = c.id AND m.content <> '' ORDER BY m.id DESC LIMIT 1) AS preview
        FROM chats c
        WHERE c.user_id = %s AND (%s::timestamptz IS NULL OR c.updated_at < %s::timestamptz)
        ORDER BY c.updated_at DESC, c.id DESC
        LIMIT %s
        """,
        (user_id, before, before, limit),
    )


async def get_chat(conn, user_id: UUID, chat_id: UUID) -> Optional[dict]:
    """The chat only if it belongs to the user; None for a missing or foreign chat."""
    return await fetch_one(
        conn,
        "SELECT " + CHAT_COLS + " FROM chats WHERE id = %s AND user_id = %s",
        (chat_id, user_id),
    )


async def chat_messages(conn, chat_id: UUID) -> List[dict]:
    return await fetch_all(
        conn,
        """
        SELECT id, role, content, finish, created_at, proposal_id FROM chat_messages
        WHERE chat_id = %s AND content <> '' ORDER BY id
        """,
        (chat_id,),
    )


async def message_count(conn, chat_id: UUID) -> int:
    row = await fetch_one(
        conn, "SELECT count(*) AS n FROM chat_messages WHERE chat_id = %s", (chat_id,)
    )
    return row["n"]


async def recent_history(conn, chat_id: UUID, limit: int) -> List[dict]:
    """Last `limit` non-empty user/assistant messages, oldest first. Tool calls are not replayed."""
    rows = await fetch_all(
        conn,
        """
        SELECT role, content FROM chat_messages
        WHERE chat_id = %s AND content <> '' ORDER BY id DESC LIMIT %s
        """,
        (chat_id, limit),
    )
    return rows[::-1]


async def add_user_message(conn, chat_id: UUID, text: str) -> int:
    row = await fetch_one(
        conn,
        "INSERT INTO chat_messages (chat_id, role, content) VALUES (%s, 'user', %s) RETURNING id",
        (chat_id, text),
    )
    await execute(
        conn,
        "UPDATE chats SET updated_at = clock_timestamp(), title = coalesce(title, %s) "
        "WHERE id = %s",
        (" ".join(text.split())[:60], chat_id),
    )
    return row["id"]


async def add_assistant_message(
    conn,
    chat_id: UUID,
    text: str,
    tool_calls: List[dict],
    prompt_id: str,
    finish: str,
    input_tokens: int,
    output_tokens: int,
) -> int:
    row = await fetch_one(
        conn,
        """
        INSERT INTO chat_messages
            (chat_id, role, content, tool_calls, prompt_id, finish, input_tokens, output_tokens)
        VALUES (%s, 'assistant', %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (
            chat_id,
            text,
            Jsonb(tool_calls) if tool_calls else None,
            prompt_id,
            finish,
            input_tokens,
            output_tokens,
        ),
    )
    await execute(conn, "UPDATE chats SET updated_at = clock_timestamp() WHERE id = %s", (chat_id,))
    return row["id"]


BRIEF_COLS = (
    "start_date, end_date, budget_kzt, has_accommodation, must_haves, interests, pace, "
    "crowd_tolerance"
)


def brief_from_row(row: Optional[dict]) -> Dict[str, Any]:
    if row is None:
        return empty_brief()
    return {key: row[key] for key in empty_brief()}


async def get_brief(conn, chat_id: UUID) -> Dict[str, Any]:
    row = await fetch_one(
        conn, "SELECT " + BRIEF_COLS + " FROM trip_briefs WHERE chat_id = %s", (chat_id,)
    )
    return brief_from_row(row)


async def lock_brief(conn, chat_id: UUID) -> Dict[str, Any]:
    """Current brief with a row lock (creates the row for chats that lack one)."""
    await execute(
        conn, "INSERT INTO trip_briefs (chat_id) VALUES (%s) ON CONFLICT DO NOTHING", (chat_id,)
    )
    row = await fetch_one(
        conn,
        "SELECT " + BRIEF_COLS + " FROM trip_briefs WHERE chat_id = %s FOR UPDATE",
        (chat_id,),
    )
    return brief_from_row(row)


async def save_brief(conn, chat_id: UUID, brief: Dict[str, Any]) -> None:
    await execute(
        conn,
        """
        UPDATE trip_briefs SET start_date = %s, end_date = %s, budget_kzt = %s,
            has_accommodation = %s, must_haves = %s, interests = %s, pace = %s,
            crowd_tolerance = %s, updated_at = now()
        WHERE chat_id = %s
        """,
        (
            brief["start_date"],
            brief["end_date"],
            brief["budget_kzt"],
            brief["has_accommodation"],
            Jsonb(brief["must_haves"]),
            Jsonb(brief["interests"]),
            brief["pace"],
            brief["crowd_tolerance"],
            chat_id,
        ),
    )


async def get_filled_order(conn, chat_id: UUID) -> List[str]:
    row = await fetch_one(
        conn, "SELECT filled_order FROM trip_briefs WHERE chat_id = %s", (chat_id,)
    )
    return list(row["filled_order"]) if row else []


async def record_filled_order(conn, chat_id: UUID, entries: List[str]) -> None:
    """Appends the entries not yet in `trip_briefs.filled_order`. Call after `lock_brief`, which
    holds the row, so two concurrent updates cannot lose each other's entries."""
    if not entries:
        return
    order = await get_filled_order(conn, chat_id)
    merged = merge_filled_order(order, entries)
    if merged != order:
        await execute(
            conn,
            "UPDATE trip_briefs SET filled_order = %s WHERE chat_id = %s",
            (Jsonb(merged), chat_id),
        )


async def graph_nodes(conn, chat_id: UUID) -> List[dict]:
    return await fetch_all(
        conn,
        "SELECT ord, kind, text FROM chat_graph_nodes WHERE chat_id = %s ORDER BY ord",
        (chat_id,),
    )


async def add_graph_node(conn, chat_id: UUID, text: str) -> Optional[dict]:
    """Append a node. Returns None for a duplicate, raises ValueError when the graph is full."""
    await execute(conn, "SELECT 1 FROM chats WHERE id = %s FOR UPDATE", (chat_id,))
    existing = await graph_nodes(conn, chat_id)
    if any(node["text"].casefold() == text.casefold() for node in existing):
        return None
    if len(existing) >= MAX_GRAPH_NODES:
        raise ValueError("the graph is full (max %d nodes)" % MAX_GRAPH_NODES)
    order = existing[-1]["ord"] + 1 if existing else 1
    return await fetch_one(
        conn,
        "INSERT INTO chat_graph_nodes (chat_id, ord, text) VALUES (%s, %s, %s) "
        "RETURNING ord, kind, text",
        (chat_id, order, text),
    )


async def try_acquire_turn(conn, chat_id: UUID, lease_sec: float) -> bool:
    """Take the chat's turn lease; False while another turn holds an unexpired one.

    The lease expires by itself (`lease_sec`), so a crashed process cannot block a chat forever.
    """
    row = await fetch_one(
        conn,
        """
        UPDATE chats SET turn_lease_until = clock_timestamp() + make_interval(secs => %s)
        WHERE id = %s AND (turn_lease_until IS NULL OR turn_lease_until < clock_timestamp())
        RETURNING id
        """,
        (lease_sec, chat_id),
    )
    return row is not None


async def release_turn(conn, chat_id: UUID) -> None:
    await execute(conn, "UPDATE chats SET turn_lease_until = NULL WHERE id = %s", (chat_id,))
