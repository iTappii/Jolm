"""The `build_trip` tool (Ш-36): plan the trip, save it, tell the client and the model.

SSE event `route_ready` (once per successful build; JSON exactly):

    {"trip_id": "<uuid>", "version": 1, "days": 3,
     "warnings": [{"code": str, "date": "YYYY-MM-DD" | null, "detail": str | null}],
     "must_have_unmet": [{"wish": str | null, "place_name": str | null, "reason": str}],
     "budget": {...}}

- `days`: number of trip days (the client reads the plan itself from `GET /v1/trips/{id}`, Ш-37).
- `warnings[].code`: `travel_estimated`, `meal_missing` (date, detail = lunch|dinner),
  `hours_assumed` (detail = number of places), `over_budget` (detail = shortfall in tenge),
  `must_haves_exceed_budget` (detail = least cost of the must-haves), `meal_prices_assumed`
  (detail = number of meals), `lodging_price_assumed`, `no_lodging_found`.
- `must_have_unmet[]`: `reason` is `no_place` (nothing in the database matches the wish; `wish`
  is set), or `closed_on_trip_days` / `no_time` (a place was found but cannot be scheduled;
  `place_name` is set). SSOT §16.11: the plan is built anyway and the AI says so.
- `budget`: see `planner.build.budget_json`. `status` "ok" | "over"; `breakdown` has
  lodging/entries/meals/transport/events in tenge; `lodging.options` (3-5, only when the tourist
  has no lodging); `variants` is null when the plan fits, else `{drop_places, cheaper}` with
  `feasible`, `total_kzt`, `saves_kzt`, `removed` / `swaps` / `lodging`; the person picks one
  with `POST /v1/trips/{id}/budget-choice`.

One trip per chat: building again after the brief changed updates the same trip (`trip_id`
stays, `version` grows). The tool result for the model is a compact day-by-day summary; every
stop has an `item_id` that the edit tools (`chat/edit_tools.py`, Ш-38) take.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from app import worker
from app.chat import edit_tools, store
from app.chat.brief import missing_fields
from app.chat.engine import ToolOutcome
from app.db import fetch_one
from app.live import clock
from app.planner.build import (
    budget_json,
    build_plan,
    must_have_unmet_json,
    trip_dates,
    warnings_json,
)
from app.planner.weather import UnknownForecast
from app.providers.weather import city_forecast
from app.routing import FakeRouter
from app.trips import store as trips_store

log = logging.getLogger(__name__)

MEMORY_NOTE_DELAY = timedelta(minutes=2)

EXPLAIN = (
    "Write a short day-by-day explanation of the plan in the person's language: for each day "
    "2-3 sentences on what they will see and why it fits them. Use only the places listed. "
    "Prices are rough estimates per person. If budget.status is 'over', say so plainly and "
    "describe the two variants (remove the least valuable places / cheaper alternatives); the "
    "person chooses in the app. If must_have_unmet is not empty, say honestly which wishes "
    "could not be included and why. Do not promise bookings."
)


def _model_budget(public: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        k: public[k]
        for k in (
            "budget_kzt", "status", "total_kzt", "shortfall_kzt", "breakdown",
            "must_haves_exceed_budget",
        )
    }  # fmt: skip
    lodging = public["lodging"]
    out["lodging"] = {
        "needed": lodging["needed"],
        "nights": lodging["nights"],
        "cost_kzt": lodging["cost_kzt"],
        "options": [
            {k: o[k] for k in ("name", "category", "price_per_night_kzt", "recommended")}
            for o in lodging.get("options", [])
        ],
    }
    if public["variants"]:
        variants = {}
        for kind, v in public["variants"].items():
            item: Dict[str, Any] = {"feasible": v["feasible"], "total_kzt": v["total_kzt"]}
            if kind == "drop_places":
                item["removed"] = [r["name"] for r in v["removed"]]
            else:
                item["swaps"] = [
                    "%s -> %s" % (s["from"]["name"], s["to"]["name"]) for s in v["swaps"]
                ]
                item["cheaper_lodging"] = v["lodging"]["name"] if v["lodging"] else None
            variants[kind] = item
        out["variants"] = variants
    return out


async def build_trip(
    db, chat_id: UUID, locale: str, router: Any, weather: Any = None
) -> ToolOutcome:
    async with db.transaction() as conn:
        brief = await store.get_brief(conn, chat_id)
        owner = await fetch_one(conn, "SELECT user_id FROM chats WHERE id = %s", (chat_id,))
    missing = missing_fields(brief)
    if missing:
        error = "the brief is incomplete; still missing: %s" % ", ".join(missing)
        return ToolOutcome({"ok": False, "error": error, "missing": missing}, ok=False, error=error)

    forecast = None
    if weather is not None:  # Ш-40: the real forecast shapes the plan; failure = plan without it
        forecast = await city_forecast(weather, trip_dates(brief))
    plan = await build_plan(db, brief, router or FakeRouter(), forecast, owner["user_id"])
    checked = None if forecast is None or isinstance(forecast, UnknownForecast) else clock.now()
    async with db.transaction() as conn:
        trip_id, version, _created = await trips_store.save_plan(
            conn, owner["user_id"], chat_id, plan, locale, weather_checked_at=checked
        )
        trip = await trips_store.get_trip_row(conn, owner["user_id"], trip_id)
        days = await edit_tools.plan_days(conn, trip, locale)  # with the item ids (Ш-38)
        await worker.enqueue(  # Ш-41: the model writes a memory note about this chat, once the
            conn,  # assistant's explanation of the plan has been saved (hence the delay)
            "memory.note",
            {"chat_id": str(chat_id), "trip_id": str(trip_id)},
            run_at=datetime.now(timezone.utc) + MEMORY_NOTE_DELAY,
            dedupe_key="memory.note:%s:v%s" % (chat_id, version),
        )

    budget = budget_json(plan, locale)
    warnings = warnings_json(plan)
    unmet = must_have_unmet_json(plan, locale)
    event = {
        "trip_id": str(trip_id),
        "version": version,
        "days": len(plan.layout.days),
        "warnings": warnings,
        "must_have_unmet": unmet,
        "budget": budget,
    }
    result = {
        "ok": True,
        "trip_id": str(trip_id),
        "version": version,
        "days": days,
        "budget": _model_budget(budget),
        "warnings": [w["code"] for w in warnings],
        "must_have_unmet": unmet,
        "instructions": EXPLAIN,
    }
    return ToolOutcome(result, [("route_ready", event)])
