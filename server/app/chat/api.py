"""Registered-user chat (Ш-31). Prefix /v1, bearer auth, a user sees only their own chats.

    POST /chats                    {"locale"?: "ru"|"en"} -> 201 chat
    GET  /chats?limit=&before=     -> {"items": [chat + preview]}, newest first
    GET  /chats/{id}               -> chat + messages + brief + graph_nodes
    POST /chats/{id}/messages      {"content": "..."} -> text/event-stream

Stream events (`event: <name>` + `data: <json>`); the stream ends with `done` or `error`:
- `text_delta`    {"text"}
- `graph_node`    {"ord", "kind", "text"}                      one node appended to the graph
- `brief_updated` {"brief": {...}, "changed": ["budget_kzt", ...]}
- `map_places`    {"reason": "must_have"|"chosen", "places": [{id, name, category, lat, lon}]}
- `route_ready`   {"trip_id", "version", "days", "warnings", "must_have_unmet", "budget"}
                  after `build_trip` (exact shape: chat/build_tool.py)
- `done`          {"message_id": n, "usage": {"input_tokens", "output_tokens"}}
- `error`         {"code", "message"}

Persistence: the user message is committed before streaming starts; brief and graph changes are
committed by the tool call that makes them; the assistant message is committed before `done`.
If the client disconnects mid-stream the model call is cancelled, but whatever was already
produced is still saved (assistant message with finish="interrupted", partial text) and the
user message and tool effects stay. A failed turn saves its partial text with finish="error".
One turn per chat at a time: a message sent while a turn is still streaming (or being saved) is
refused with 409 `chat_busy` right away (no waiting). The turn takes a lease on the chat row
(`chats.turn_lease_until`, migration 0010) and clears it in the same transaction that saves the
assistant message; the lease also expires on its own after LEASE_SEC, so a crash or a response
that never started cannot lock a chat for good. Refusals (401/404/409/429/503) do not hold or
consume anything: the chat_full check comes first, then the lease, then the rate limit.
The brief reaches the model as a separate `<trip_brief_data>` message, never inside the system
prompt, so words typed by the tourist are not promoted to instructions.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.auth import sessions
from app.auth.api import bearer_token
from app.chat import build_tool, store, tools
from app.chat.brief import (
    BriefError,
    BriefUpdate,
    apply_update,
    brief_data_block,
    public_brief,
    today_almaty,
)
from app.chat.deps import make_llm
from app.chat.engine import ToolOutcome, TurnRecord, run_turn
from app.chat.prompts import TRIP_BRIEF, load_prompt
from app.chat.ratelimit import acquire
from app.chat.sse import format_event, sse_response
from app.config import get_settings
from app.errors import AppError
from app.providers.llm import Message, ToolArgsError, ToolCall, parse_tool_args

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["chat"])

MAX_MESSAGE_CHARS = 4000
MAX_CHAT_MESSAGES = 400  # user + assistant messages per chat
HISTORY_MESSAGES = 30  # replayed to the model
HISTORY_CHARS = 20_000
MAX_TOOL_ROUNDS = 5


def lease_sec() -> float:
    """Upper bound of one turn: every model round may take the full timeout (no retries)."""
    return (MAX_TOOL_ROUNDS + 1) * get_settings().llm_timeout_sec + 30


_background: Set["asyncio.Future[Any]"] = set()  # keeps detached writes alive until they finish


class CreateChat(BaseModel):
    locale: Optional[str] = Field(None, pattern="^(ru|en)$")


class SendMessage(BaseModel):
    content: str = Field(max_length=MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value.strip()


def _chat_json(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "locale": row["locale"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def _own_chat(conn, user_id: UUID, chat_id: UUID) -> dict:
    row = await store.get_chat(conn, user_id, chat_id)
    if row is None:  # not found and foreign look the same
        raise AppError(404, "not_found")
    return row


@router.post("/chats", status_code=201)
async def create_chat(request: Request, payload: Optional[CreateChat] = None):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        locale = (payload.locale if payload else None) or user["locale"]
        row = await store.create_chat(conn, user["id"], locale)
    return _chat_json(row)


@router.get("/chats")
async def list_chats(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    before: Optional[datetime] = Query(None),  # noqa: B008  updated_at cursor of last item
):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        rows = await store.list_chats(conn, user["id"], limit, before)
    items = []
    for row in rows:
        item = _chat_json(row)
        item["preview"] = (row["preview"] or "")[:120] or None
        items.append(item)
    return {"items": items}


@router.get("/chats/{chat_id}")
async def get_chat(chat_id: UUID, request: Request):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        chat = await _own_chat(conn, user["id"], chat_id)
        messages = await store.chat_messages(conn, chat_id)
        brief = await store.get_brief(conn, chat_id)
        nodes = await store.graph_nodes(conn, chat_id)
    return dict(
        _chat_json(chat),
        messages=[
            {k: m[k] for k in ("id", "role", "content", "finish", "created_at")} for m in messages
        ],
        brief=public_brief(brief),
        graph_nodes=nodes,
    )


def _trim_history(rows: List[dict]) -> List[Message]:
    kept: List[dict] = []
    total = 0
    for row in reversed(rows):
        total += len(row["content"])
        if kept and total > HISTORY_CHARS:
            break
        kept.append(row)
    kept.reverse()
    while (
        kept and kept[0]["role"] != "user"
    ):  # providers expect the history to open with a user turn
        kept.pop(0)
    return [Message(role=r["role"], content=r["content"]) for r in kept]


@router.post("/chats/{chat_id}/messages")
async def send_message(chat_id: UUID, payload: SendMessage, request: Request):
    access = bearer_token(request)
    db = request.app.state.db
    async with db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        chat = await _own_chat(conn, user["id"], chat_id)
        llm = make_llm(request)
        if await store.message_count(conn, chat_id) >= MAX_CHAT_MESSAGES:
            raise AppError(409, "chat_full")  # before the rate limit: a refusal costs nothing
        # Taken inside this transaction: any refusal below rolls the lease back with it.
        if not await store.try_acquire_turn(conn, chat_id, lease_sec()):
            raise AppError(409, "chat_busy")
        wait = acquire([(request.app.state.chat_limiters.user, "user:%s" % user["id"])])
        if wait is not None:
            raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)})
        await store.add_user_message(conn, chat_id, payload.content)
        history = _trim_history(await store.recent_history(conn, chat_id, HISTORY_MESSAGES))
        brief = await store.get_brief(conn, chat_id)

    locale = chat["locale"]
    prompt = load_prompt(TRIP_BRIEF, locale)
    system = prompt.render(today_almaty())  # static per prompt version; no user text in it
    history.insert(0, Message(role="user", content=brief_data_block(brief)))
    record = TurnRecord()

    async def handle_tool(call: ToolCall) -> ToolOutcome:
        handler = {
            tools.UPDATE_TRIP_BRIEF: _update_trip_brief,
            tools.ADD_GRAPH_NODE: _add_graph_node,
            tools.SEARCH_PLACES: _search_places,
            tools.BUILD_TRIP: lambda *a: _build_trip(
                *a, getattr(request.app.state, "routing_provider", None)
            ),
        }.get(call.name)
        if handler is None:
            return ToolOutcome({"error": "unknown tool %r" % call.name}, ok=False, error="unknown")
        try:
            return await handler(db, chat_id, locale, call)
        except ToolArgsError as exc:
            return ToolOutcome({"ok": False, "error": str(exc)}, ok=False, error=str(exc))

    async def save(finish: str) -> Optional[int]:
        """Store the assistant message and release the chat's turn lease, atomically."""
        try:
            async with db.transaction() as conn:
                message_id = None
                if record.text or record.tool_calls:
                    message_id = await store.add_assistant_message(
                        conn,
                        chat_id,
                        record.text,
                        record.tool_calls,
                        prompt.id,
                        finish,
                        record.usage.input_tokens,
                        record.usage.output_tokens,
                    )
                await store.release_turn(conn, chat_id)
                return message_id
        except Exception:
            try:  # the save failed: at least free the chat (otherwise the lease expires alone)
                async with db.transaction() as conn:
                    await store.release_turn(conn, chat_id)
            except Exception:
                log.exception("could not release the chat turn lease")
            raise

    async def frames():
        saved = False
        turn = run_turn(
            llm,
            history,
            [
                tools.UPDATE_TRIP_BRIEF_SPEC,
                tools.ADD_GRAPH_NODE_SPEC,
                tools.SEARCH_PLACES_SPEC,
                tools.BUILD_TRIP_SPEC,
            ],
            system,
            handle_tool,
            record,
            locale,
            MAX_TOOL_ROUNDS,
        )
        try:
            async for name, data in turn:
                if name != "error":  # sent after the message is saved
                    yield format_event(name, data)
            await turn.aclose()
            message_id = await save("error" if record.error else "stop")
            saved = True
            if record.error:
                yield format_event("error", record.error)
            else:
                usage = {
                    "input_tokens": record.usage.input_tokens,
                    "output_tokens": record.usage.output_tokens,
                }
                yield format_event("done", {"message_id": message_id, "usage": usage})
        finally:
            if not saved:  # client disconnected (or a save failed): keep what was produced
                await _save_detached(turn, save("error" if record.error else "interrupted"))

    return sse_response(frames())


async def _save_detached(turn, coro) -> None:
    """Finish the save even if this task is being cancelled (client went away)."""
    task = asyncio.ensure_future(_finish(turn, coro))
    _background.add(task)
    task.add_done_callback(_background.discard)
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        pass  # the write continues in `task`; the original cancellation keeps propagating
    except Exception:
        log.exception("could not save an interrupted chat turn")


async def _finish(turn, coro) -> None:
    await turn.aclose()  # runs run_turn's cleanup, which fills in the token usage
    await coro


# --- tools ----------------------------------------------------------------------------------


async def _update_trip_brief(db, chat_id: UUID, locale: str, call: ToolCall) -> ToolOutcome:
    args = parse_tool_args(call, BriefUpdate)
    async with db.transaction() as conn:
        current = await store.lock_brief(conn, chat_id)
        try:
            new, changed = apply_update(current, args, today_almaty())
        except BriefError as exc:
            return ToolOutcome({"ok": False, "error": str(exc)}, ok=False, error=str(exc))
        if changed:
            await store.save_brief(conn, chat_id, new)
    result = {"ok": True, "changed": changed, "brief": public_brief(new)}
    events = []
    if changed:
        events.append(("brief_updated", {"brief": public_brief(new), "changed": changed}))
        known = {item.casefold() for item in current["must_haves"]}
        pins: List[Dict[str, Any]] = []
        for wish in new["must_haves"]:
            if wish.casefold() in known:
                continue
            _, found = await tools.search_places(
                db, tools.SearchPlacesArgs(query=wish, limit=1), locale
            )
            pins.extend(dict(pin, must_have=wish) for pin in found)
        if pins:
            events.append(("map_places", {"reason": "must_have", "places": pins}))
    return ToolOutcome(result, events)


async def _add_graph_node(db, chat_id: UUID, locale: str, call: ToolCall) -> ToolOutcome:
    args = parse_tool_args(call, tools.AddGraphNodeArgs)
    text = " ".join(args.text.split())
    if not text:
        return ToolOutcome({"ok": False, "error": "text is empty"}, ok=False, error="empty text")
    try:
        async with db.transaction() as conn:
            node = await store.add_graph_node(conn, chat_id, text)
    except ValueError as exc:
        return ToolOutcome({"ok": False, "error": str(exc)}, ok=False, error=str(exc))
    if node is None:
        return ToolOutcome({"ok": True, "note": "this node already exists"})
    return ToolOutcome({"ok": True, "ord": node["ord"]}, [("graph_node", dict(node))])


async def _search_places(db, chat_id: UUID, locale: str, call: ToolCall) -> ToolOutcome:
    args = parse_tool_args(call, tools.SearchPlacesArgs)
    result, pins = await tools.search_places(db, args, locale)
    events = []
    if pins and args.show_on_map:
        events.append(("map_places", {"reason": "chosen", "places": pins}))
    return ToolOutcome(result, events)


async def _build_trip(db, chat_id: UUID, locale: str, call: ToolCall, router: Any) -> ToolOutcome:
    """Plan, save and announce the trip (Ш-36); see `chat/build_tool.py` for the event shape."""
    return await build_tool.build_trip(db, chat_id, locale, router)
