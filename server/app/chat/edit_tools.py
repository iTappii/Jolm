"""Chat tools that read and edit the trip of the chat (Ш-38): `get_trip_plan`,
`remove_trip_item`, `replace_trip_item`.

The model sees the plan as a compact day-by-day list with `item_id`s (also returned by
`build_trip`), changes it through the tools, and the engine (`app.trips.edit`) re-times the day.
Each successful edit sends one SSE event (exact JSON):

    event: trip_updated
    {"trip_id": "<uuid>", "version": 3, "action": "remove" | "replace",
     "changed_days": ["2026-12-05"],
     "budget": {"status": "ok" | "over", "total_kzt": int, "remaining_kzt": int}}

The client reloads `GET /v1/trips/{id}` for the changed days. A must-have stop is refused
(`error: "must_have"`) until the person confirms; then the model calls again with `force: true`.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.chat.engine import ToolOutcome
from app.db import fetch_one
from app.errors import AppError
from app.i18n import translate
from app.planner.build import place_name
from app.providers.llm import ToolSpec, parse_tool_args
from app.trips import edit, read, store

log = logging.getLogger(__name__)

GET_TRIP_PLAN = "get_trip_plan"
REMOVE_TRIP_ITEM = "remove_trip_item"
REPLACE_TRIP_ITEM = "replace_trip_item"
EDIT_TOOLS = (GET_TRIP_PLAN, REMOVE_TRIP_ITEM, REPLACE_TRIP_ITEM)

CONFIRM_HINT = (
    "This stop is one of the person's must-haves. Ask them to confirm they really want it "
    "changed; only after a clear yes call the tool again with force=true."
)


class NoArgs(BaseModel):
    pass


class RemoveTripItemArgs(BaseModel):
    item_id: UUID = Field(description="item_id of the stop, from get_trip_plan or build_trip")
    force: bool = Field(False, description="Only after the person confirmed (must-have stops)")


class ReplaceTripItemArgs(BaseModel):
    item_id: UUID = Field(description="item_id of the stop to replace")
    place_id: Optional[UUID] = Field(None, description="Exact replacement place id")
    category: Optional[str] = Field(None, max_length=64, description="Category slug, e.g. park")
    query: Optional[str] = Field(None, max_length=100, description="Part of a place name")
    force: bool = Field(False, description="Only after the person confirmed (must-have stops)")


GET_TRIP_PLAN_SPEC = ToolSpec.from_model(
    GET_TRIP_PLAN,
    "Read the current plan of this chat's trip, day by day, with item_id of every stop. Call it "
    "before editing the plan in a later message.",
    NoArgs,
)
REMOVE_TRIP_ITEM_SPEC = ToolSpec.from_model(
    REMOVE_TRIP_ITEM,
    "Remove one stop from the built plan; its day is re-timed, the rest of the trip is kept. "
    "Use it instead of build_trip for a single change.",
    RemoveTripItemArgs,
)
REPLACE_TRIP_ITEM_SPEC = ToolSpec.from_model(
    REPLACE_TRIP_ITEM,
    "Replace one stop of the built plan with another place: give exactly one of place_id, "
    "category (slug) or query (name part). The day is re-timed, the rest is kept.",
    ReplaceTripItemArgs,
)
EDIT_SPECS: List[ToolSpec] = [GET_TRIP_PLAN_SPEC, REMOVE_TRIP_ITEM_SPEC, REPLACE_TRIP_ITEM_SPEC]


async def plan_days(conn, trip: Dict[str, Any], locale: str, only: Optional[List[str]] = None):
    """Compact plan for the model: `[{date, stops: [{item_id, time, name, kind, category,
    cost_kzt, meal?, must_have?}]}]`; `only` = ISO dates to include."""
    items = await store.main_items(conn, trip["id"])
    days = []
    for d in read.trip_dates(trip["start_date"], trip["end_date"]):
        if only is not None and d.isoformat() not in only:
            continue
        stops = []
        for row in (r for r in items if r["day"] == d):
            stop: Dict[str, Any] = {
                "item_id": str(row["id"]),
                "time": read.local(row["starts_at"])[11:16],
                "name": place_name(_Names(row), locale),
                "kind": row["kind"],
                "category": row["category"],
                "cost_kzt": row["est_cost_kzt"],
            }
            if row["meal"]:
                stop["meal"] = row["meal"]
            if row["is_must_have"]:
                stop["must_have"] = True
            stops.append(stop)
        days.append({"date": d.isoformat(), "stops": stops})
    return days


class _Names:  # `planner.build.place_name` reads name_ru / name_en attributes
    def __init__(self, row: Dict[str, Any]):
        self.name_ru, self.name_en = row["name_ru"], row["name_en"]


async def _chat_trip(conn, chat_id: UUID) -> Optional[Dict[str, Any]]:
    """(user, trip) of the chat, or None before a trip was built."""
    row = await fetch_one(
        conn,
        "SELECT c.user_id, t.id AS trip_id FROM chats c JOIN trips t ON t.chat_id = c.id "
        "WHERE c.id = %s",
        (chat_id,),
    )
    return row


def _no_trip() -> ToolOutcome:
    error = "no trip is built in this chat yet; call build_trip first"
    return ToolOutcome({"ok": False, "error": error}, ok=False, error=error)


def _refused(exc: AppError, locale: str) -> ToolOutcome:
    result: Dict[str, Any] = {
        "ok": False,
        "error": exc.code,
        "message": exc.message or translate(exc.code, locale),
    }
    if exc.code == "must_have":
        result["hint"] = CONFIRM_HINT
    return ToolOutcome(result, ok=False, error=exc.code)


async def _after_edit(db, chat_id: UUID, locale: str, outcome: Dict[str, Any]) -> ToolOutcome:
    """Model result + the `trip_updated` event for a successful edit."""
    async with db.transaction() as conn:
        found = await _chat_trip(conn, chat_id)
        trip = await store.get_trip_row(conn, found["user_id"], found["trip_id"])
        days = await plan_days(conn, trip, locale, only=outcome["changed_days"])
    budget = outcome["budget"]
    event = {
        "trip_id": outcome["trip_id"],
        "version": outcome["version"],
        "action": outcome["action"],
        "changed_days": outcome["changed_days"],
        "budget": {k: budget[k] for k in ("status", "total_kzt", "remaining_kzt")},
    }
    result = dict(outcome, ok=True, days=days)
    result["warnings"] = [w["code"] for w in trip["warnings"]]
    return ToolOutcome(result, [("trip_updated", event)])


async def get_trip_plan(db, chat_id: UUID, locale: str, call: Any) -> ToolOutcome:
    parse_tool_args(call, NoArgs)
    async with db.transaction() as conn:
        found = await _chat_trip(conn, chat_id)
        if found is None:
            return _no_trip()
        trip = await store.get_trip_row(conn, found["user_id"], found["trip_id"])
        days = await plan_days(conn, trip, locale)
    budget = trip["budget"] or {}
    return ToolOutcome(
        {
            "ok": True,
            "trip_id": str(trip["id"]),
            "version": trip["version"],
            "days": days,
            "budget": {k: budget.get(k) for k in ("budget_kzt", "status", "total_kzt")},
        }
    )


async def remove_trip_item(db, chat_id: UUID, locale: str, call: Any, router: Any) -> ToolOutcome:
    args = parse_tool_args(call, RemoveTripItemArgs)
    try:
        async with db.transaction() as conn:
            found = await _chat_trip(conn, chat_id)
            if found is None:
                return _no_trip()
            outcome = await edit.remove_item(
                conn, router, found["user_id"], found["trip_id"], args.item_id, locale, args.force
            )
    except AppError as exc:
        return _refused(exc, locale)
    return await _after_edit(db, chat_id, locale, outcome)


async def replace_trip_item(db, chat_id: UUID, locale: str, call: Any, router: Any) -> ToolOutcome:
    args = parse_tool_args(call, ReplaceTripItemArgs)
    try:
        async with db.transaction() as conn:
            found = await _chat_trip(conn, chat_id)
            if found is None:
                return _no_trip()
            outcome = await edit.replace_item(
                conn, router, found["user_id"], found["trip_id"], args.item_id, locale,
                place_id=args.place_id, category=args.category, query=args.query,
                force=args.force,
            )  # fmt: skip
    except AppError as exc:
        return _refused(exc, locale)
    return await _after_edit(db, chat_id, locale, outcome)
