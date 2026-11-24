"""Registered-user chat (Ш-31). Prefix /v1, bearer auth, a user sees only their own chats.

    POST /chats                    {"locale"?: "ru"|"en"} -> 201 chat
    GET  /chats?limit=&before=     -> {"items": [chat + preview]}, newest first
    GET  /chats/{id}               -> chat + messages + brief + graph_nodes + live_route (or null)
    POST /chats/{id}/live-route/choose  {"ord", "place_id"} -> live_route (Ш-54)
    POST /chats/{id}/messages      {"content": "..."} -> text/event-stream
    GET  /chats/{id}/events        -> text/event-stream of live-route updates (Ш-64)

Stream events (`event: <name>` + `data: <json>`); the stream ends with `done` or `error`:
- `text_delta`    {"text"}
- `graph_node`    {"ord", "kind", "text"}                      one node appended to the graph
- `brief_updated` {"brief": {...}, "changed": ["budget_kzt", ...]}
- `map_places`    {"reason": "must_have"|"chosen", "places": [{id, name, category, lat, lon}]}
- `live_route_status` {"state": "building"|"ready"|"failed"} (Ш-64) the live route is built in
                  the BACKGROUND: `building` follows `brief_updated` when must-have wishes changed
                  and the model does not wait for it. `ready` / `failed` come on the events stream
                  (GET /chats/{id}/events), or in this stream right before `done` when the pass
                  happened to end earlier (never waited for)
- `live_route`    {"stops": [...], "legs": [...]} the whole live route (exact shape and rules:
                  chat/live_route.py, Ш-54); with `live_route_status` `ready` as above
- `route_ready`   {"trip_id", "version", "days", "warnings", "must_have_unmet", "budget"}
                  after `build_trip` (exact shape: chat/build_tool.py)
- `trip_updated`  {"trip_id", "version", "action", "changed_days", "budget"}
                  after `remove_trip_item` / `replace_trip_item` (exact shape: chat/edit_tools.py)
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
Events stream (Ш-64): `GET /chats/{id}/events`, same auth and ownership as `GET /chats/{id}`.
It sends at once the snapshot `live_route` + `live_route_status` (`building` while a pass of this
chat runs on this worker, else `ready`), then `live_route` + `live_route_status` after every
announcement (Postgres NOTIFY, see chat/events_bus.py) of the chat, `: keepalive` comments every
15 s, and ends after 10 minutes (the client reconnects and gets a fresh snapshot).
The brief reaches the model as a separate `<trip_brief_data>` message, never inside the system
prompt, so words typed by the tourist are not promoted to instructions. Memory (Ш-41: notes of
earlier chats, rejected and favourite categories) comes the same way, as a `<user_memory_data>`
message before it, and only when there is something to say.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator

from app import llm_budget
from app.analytics import service as analytics
from app.auth import sessions
from app.auth.api import bearer_token
from app.chat import build_tool, edit_tools, events_bus, live_bg, live_route, store, tools
from app.chat.brief import (
    BriefError,
    BriefUpdate,
    apply_update,
    brief_data_block,
    fill_entries,
    public_brief,
    today_in_region,
)
from app.chat.deps import make_llm
from app.chat.engine import ToolOutcome, TurnRecord, run_turn
from app.chat.prompts import TRIP_BRIEF, load_prompt
from app.chat.sse import format_event, sse_response
from app.config import get_settings
from app.db import fetch_one
from app.errors import AppError
from app.live import clock
from app.memory import affinity
from app.memory.notes import latest_notes, memory_data_block
from app.planner.candidates import far_place
from app.planner.outside import outside_wish
from app.providers.llm import Message, ToolArgsError, ToolCall, parse_tool_args
from app.ratelimit import acquire
from app.routing import FakeRouter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["chat"])

MAX_MESSAGE_CHARS = 4000
MAX_CHAT_MESSAGES = 400  # user + assistant messages per chat
HISTORY_MESSAGES = 30  # replayed to the model
HISTORY_CHARS = 20_000
MAX_TOOL_ROUNDS = 5


EVENTS_KEEPALIVE_SEC = 15.0
EVENTS_MAX_SEC = 600.0  # the events stream ends after this long; the client reconnects


def scheduler_of(app) -> live_bg.LiveRouteScheduler:
    """Background live-route passes of this process (created on first use, closed in lifespan)."""
    if getattr(app.state, "live_routes", None) is None:
        app.state.live_routes = live_bg.LiveRouteScheduler()
    return app.state.live_routes


def bus_of(app) -> events_bus.ChatEventBus:
    """The one LISTEN connection of this process (opened on the first events subscription)."""
    if getattr(app.state, "chat_event_bus", None) is None:
        app.state.chat_event_bus = events_bus.ChatEventBus(getattr(app.state, "listen_url", None))
    return app.state.chat_event_bus


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
        filled_order = await store.get_filled_order(conn, chat_id)
        nodes = await store.graph_nodes(conn, chat_id)
        live = await live_route.load(conn, chat_id, chat["locale"])
    return dict(
        _chat_json(chat),
        messages=[
            {k: m[k] for k in ("id", "role", "content", "finish", "created_at", "proposal_id")}
            for m in messages
        ],
        brief=dict(public_brief(brief), filled_order=filled_order),
        graph_nodes=nodes,
        live_route=live,
    )


class ChooseStop(BaseModel):
    ord: int = Field(ge=1)
    place_id: UUID


@router.post("/chats/{chat_id}/live-route/choose")
async def choose_live_stop(chat_id: UUID, payload: ChooseStop, request: Request):
    """An alternative becomes the stop; legs are recomputed. 404 unknown chat/ord, 409 while a
    turn is running on the chat, 422 the place is not that stop's place or alternative."""
    access = bearer_token(request)
    db = request.app.state.db
    async with db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        chat = await _own_chat(conn, user["id"], chat_id)
        busy = await fetch_one(
            conn,
            "SELECT 1 AS busy FROM chats WHERE id = %s AND turn_lease_until > clock_timestamp()",
            (chat_id,),
        )
    if busy:
        raise AppError(409, "chat_busy")
    routing = getattr(request.app.state, "routing_provider", None) or FakeRouter()
    try:
        route = await live_route.choose(
            db, chat_id, chat["locale"], routing, payload.ord, payload.place_id
        )
    except live_route.ChoiceError as exc:
        raise AppError(exc.status, exc.code) from None
    await events_bus.publish(db, chat_id, "live_route")  # Ш-64: other open screens update too
    return route


def _route_json(route: Optional[dict]) -> dict:
    return route or {"stops": [], "legs": []}


@router.get("/chats/{chat_id}/events")
async def chat_events(chat_id: UUID, request: Request):
    """Live-route updates of an open chat (Ш-64); see the module docstring."""
    access = bearer_token(request)
    db = request.app.state.db
    async with db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        chat = await _own_chat(conn, user["id"], chat_id)
    scheduler, bus = scheduler_of(request.app), bus_of(request.app)

    async def read_route() -> dict:
        async with db.transaction() as conn:
            return _route_json(await live_route.load(conn, chat_id, chat["locale"]))

    async def frames():
        loop = asyncio.get_running_loop()
        deadline = loop.time() + EVENTS_MAX_SEC
        async with bus.subscribe(chat_id) as queue:  # before the snapshot: nothing is missed
            yield format_event("live_route", await read_route())
            state = "building" if scheduler.is_building(chat_id) else "ready"
            yield format_event("live_route_status", {"state": state})
            while True:
                left = deadline - loop.time()
                if left <= 0:
                    return
                try:
                    kind = await asyncio.wait_for(queue.get(), min(EVENTS_KEEPALIVE_SEC, left))
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if kind == "building":
                    yield format_event("live_route_status", {"state": "building"})
                elif kind == "failed":
                    yield format_event("live_route_status", {"state": "failed"})
                else:  # live_route / resync: the stored route is the truth
                    yield format_event("live_route", await read_route())
                    if kind == "resync" and scheduler.is_building(chat_id):
                        state = "building"
                    else:
                        state = "ready"
                    yield format_event("live_route_status", {"state": state})

    return sse_response(frames())


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
        # Ш-66: daily token budgets (user, whole service), before anything is counted or called
        budgets = llm_budget.user_budgets(get_settings(), user["id"])
        await llm_budget.check(conn, budgets)
        # Taken inside this transaction: any refusal below rolls the lease back with it.
        if not await store.try_acquire_turn(conn, chat_id, lease_sec()):
            raise AppError(409, "chat_busy")
        wait = await acquire(conn, [(request.app.state.chat_limiters.user, "user:%s" % user["id"])])
        if wait is not None:
            raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)})
        await store.add_user_message(conn, chat_id, payload.content)
        history = _trim_history(await store.recent_history(conn, chat_id, HISTORY_MESSAGES))
        brief = await store.get_brief(conn, chat_id)
        memory = await affinity.load_memory(conn, user["id"])
        memory_block = memory_data_block(await latest_notes(conn, user["id"]), memory)

    locale = chat["locale"]
    prompt = load_prompt(TRIP_BRIEF, locale)
    system = prompt.render(today_in_region())  # static per prompt version; no user text in it
    history.insert(0, Message(role="user", content=brief_data_block(brief)))
    if memory_block is not None:  # Ш-41: data for the model, like the brief, never in `system`
        history.insert(0, Message(role="user", content=memory_block))
    record = TurnRecord()
    turn_started = time.perf_counter()

    router = getattr(request.app.state, "routing_provider", None) or FakeRouter()
    weather = getattr(request.app.state, "weather_provider", None)  # None: plan without forecast
    live = live_bg.TurnLive(scheduler_of(request.app), db, chat_id, locale, router)

    async def handle_tool(call: ToolCall) -> ToolOutcome:
        handler = {
            tools.UPDATE_TRIP_BRIEF: lambda *a: _update_trip_brief(*a, live),
            tools.ADD_GRAPH_NODE: _add_graph_node,
            tools.SEARCH_PLACES: _search_places,
            tools.SEARCH_EVENTS: _search_events,
            tools.BUILD_TRIP: lambda *a: _build_trip(*a, router, weather, live),
            edit_tools.GET_TRIP_PLAN: edit_tools.get_trip_plan,
            edit_tools.REMOVE_TRIP_ITEM: lambda *a: edit_tools.remove_trip_item(*a, router),
            edit_tools.REPLACE_TRIP_ITEM: lambda *a: edit_tools.replace_trip_item(*a, router),
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
                await llm_budget.record(conn, budgets, record.usage.total, get_settings())
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
                tools.SEARCH_EVENTS_SPEC,
                tools.BUILD_TRIP_SPEC,
                *edit_tools.EDIT_SPECS,
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
            _log_turn(record, turn_started)
            if record.error:
                yield format_event("error", record.error)
            else:
                for name, data in _finished_route_events(live):
                    yield format_event(name, data)
                usage = {
                    "input_tokens": record.usage.input_tokens,
                    "output_tokens": record.usage.output_tokens,
                }
                yield format_event("done", {"message_id": message_id, "usage": usage})
        finally:
            if not saved:  # client disconnected (or a save failed): keep what was produced
                await _save_detached(turn, save("error" if record.error else "interrupted"))

    return sse_response(frames())


def _finished_route_events(live: live_bg.TurnLive) -> list:
    """Ш-64: if the background pass of this turn already ended, say so before `done` (never wait:
    otherwise the events stream carries it). No pass or a pass still running: nothing."""
    result = live.finished()
    if result is None:
        return []
    if not result.ok:
        return [("live_route_status", {"state": "failed"})]
    events = []
    pins = [dict(pin, must_have=wish) for wish, pin in result.pins.items()]
    if pins:  # old clients: the best match of every new wish
        events.append(("map_places", {"reason": "must_have", "places": pins}))
    events.append(("live_route", _route_json(result.route)))
    events.append(("live_route_status", {"state": "ready"}))
    return events


def _log_turn(record: TurnRecord, started: float) -> None:
    """One structured line per turn: durations in ms, no text and no ids."""
    log.info(
        "chat turn timing",
        extra={
            "first_text_ms": record.first_text_ms,
            "llm_rounds_ms": record.llm_rounds_ms,
            "tools_ms": record.tools_ms,
            "total_ms": round((time.perf_counter() - started) * 1000),
            "error": record.error is not None,
        },
    )


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


async def _update_trip_brief(
    db, chat_id: UUID, locale: str, call: ToolCall, live: live_bg.TurnLive
) -> ToolOutcome:
    args = parse_tool_args(call, BriefUpdate)
    async with db.transaction() as conn:
        current = await store.lock_brief(conn, chat_id)
        try:
            new, changed = apply_update(current, args, today_in_region())
        except BriefError as exc:
            return ToolOutcome({"ok": False, "error": str(exc)}, ok=False, error=str(exc))
        far = await _new_outside_wishes(conn, current, new) if "must_haves" in changed else []
        if changed:
            await store.save_brief(conn, chat_id, new)
            await store.record_filled_order(conn, chat_id, fill_entries(current, new, changed))
        for _, place in far:  # Ш-56: demand by region, without who asked or their words
            await analytics.record_server(
                conn, "wish_outside_area", clock.now(), props={"place": place.id}
            )
    result = {"ok": True, "changed": changed, "brief": public_brief(new)}
    if far:  # the model says honestly that v1 plans one region only (prompt v5)
        result["outside_area"] = [dict(place.as_json(locale), wish=wish) for wish, place in far]
    events = []
    if changed:
        events.append(("brief_updated", {"brief": public_brief(new), "changed": changed}))
        if "must_haves" in changed:  # Ш-54 / Ш-64: the route follows in the background
            live.schedule()  # returns at once; the model must not wait for the map
            events.append(("live_route_status", {"state": "building"}))
            result["live_route"] = "building"
    return ToolOutcome(result, events)


async def _new_outside_wishes(conn, current: dict, new: dict) -> list:
    """(wish, known place) for each must-have this update added that names a known place Jol has
    no data for (Ш-56; Ш-62: a place of the country that the database has is plannable, so it is
    not reported). A wish that was already in the brief is not counted again."""
    known = {item.casefold() for item in current.get("must_haves") or []}
    out = []
    for wish in new.get("must_haves") or []:
        place = None if wish.casefold() in known else outside_wish(wish)
        if place is not None and await far_place(conn, wish, place) is None:
            out.append((wish, place))
    return out


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


async def _search_events(db, chat_id: UUID, locale: str, call: ToolCall) -> ToolOutcome:
    """Events of the trip dates (or the window the model asks for); no SSE event."""
    args = parse_tool_args(call, tools.SearchEventsArgs)
    async with db.transaction() as conn:
        brief = await store.get_brief(conn, chat_id)
    result = await tools.search_events(
        db, args, locale, brief.get("start_date"), brief.get("end_date"), brief.get("pace")
    )
    return ToolOutcome(result)


async def _build_trip(
    db,
    chat_id: UUID,
    locale: str,
    call: ToolCall,
    router: Any,
    weather: Any = None,
    live: Optional[live_bg.TurnLive] = None,
) -> ToolOutcome:
    """Plan, save and announce the trip (Ш-36); see `chat/build_tool.py` for the event shape.
    The planner takes the stops picked on the live route (Ш-54), so a background pass that is
    still running for this chat is awaited first (Ш-64)."""
    if live is not None:
        await live.wait_idle()
    return await build_tool.build_trip(db, chat_id, locale, router, weather)
