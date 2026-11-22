"""Trip edits (Ш-38): remove or replace a stop, choose a transport mode for a leg.

An edit re-times ONE day (`planner.layout.retime_day`): the stops the person saw keep their
order, transitions are rebuilt with real legs, the other days are not touched, the whole planner
is not re-run. The trip's `version` grows by one; `changed_days` tell the client what to reload.
Everything runs in the caller's transaction, in two phases (plan-then-apply, Ш-38 coordinator
№1 / Ш-40 №3): first the plan is computed with NO row lock (all router and Valhalla calls
happen here, reading the trip by `version`), then the trip row is locked (`FOR UPDATE`), its
`version` is compared with the planned one and only the writes are done under the lock. If the
trip changed in between, nothing is written and `AppError(409, "trip_changed")` is raised; the
API retries the whole request once (a fresh transaction, so the lock is released) and answers
409 `trip_changed` when it changes again.

Decisions (docs/adr/0003-open-defaults.md):
- A must-have stop is not removed or replaced unless `force` is true (409 `must_have` otherwise):
  SSOT §4 says explicit wishes are guaranteed, but the person is the boss of their own plan, so a
  deliberate `force` is honoured and recorded in `must_have_unmet` (`removed_by_user` /
  `replaced_by_user`). The brief still lists the wish, so a full rebuild would bring it back.
- Over-budget variants (SSOT §5.2) are made from the plan as it was; after an edit they are
  stale, so they are deleted and `budget.variants` becomes null (the choice is no longer open).
- Each removal / replacement writes a memory signal (`user_place_signals`, SSOT §8) for Ш-41.
- Transport choices the person made survive a re-timing of their day (same from/to places).
- Choosing a transport mode does not re-time the day (see `set_leg_mode`).
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import execute, fetch_all, fetch_one
from app.errors import AppError
from app.places import service
from app.planner import hours as hrs
from app.planner import sql as planner_sql
from app.planner.area import ALMATY_BBOX, ALMATY_CENTRE
from app.planner.build import leg_tools
from app.planner.layout import NON_MEAL_CATEGORIES, KeptStop, RetimedDay, retime_day
from app.planner.model import Place, place_from_row
from app.planner.travel import PreferredLegs
from app.routing.base import Point, RoutingUnavailable
from app.routing.fake import haversine_m
from app.routing.service import get_directions
from app.trips import read, store

log = logging.getLogger(__name__)

MAX_REPLACEMENT_TRIES = 5  # candidates tried (each is one re-timing of the day)
CANDIDATE_POOL = 40
MUST_HAVE_UNMET_REMOVED = "removed_by_user"
MUST_HAVE_UNMET_REPLACED = "replaced_by_user"


# --- budget -----------------------------------------------------------------------------
def budget_summary(budget: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": budget.get("status"),
        "total_kzt": budget.get("total_kzt"),
        "remaining_kzt": budget.get("remaining_kzt"),
        "shortfall_kzt": budget.get("shortfall_kzt"),
        "breakdown": budget.get("breakdown"),
    }


def _set_warning(warnings: List[dict], code: str, detail: Optional[str]) -> None:
    """Replace the date-less warning `code` (add it when `detail` is not None, drop it if None)."""
    warnings[:] = [w for w in warnings if not (w["code"] == code and w.get("date") is None)]
    if detail is not None:
        warnings.append({"code": code, "date": None, "detail": detail})


async def recompute_budget(
    conn, trip: Dict[str, Any], warnings: List[dict]
) -> Tuple[Dict[str, Any], int]:
    """New stored budget block and total from the rows of the plan; updates `warnings`.

    Same rules as `planner.budget.plan_costs`: a meal (kind meal or a food place) counts as a
    meal, the rest as entries, transport is the sum of the legs' costs (their chosen options).
    Lodging stays as stored. Over-budget variants are dropped (they were built for the old plan).
    """
    items = await store.main_items(conn, trip["id"])
    legs = await store.main_legs(conn, trip["id"])
    stored = dict(trip["budget"] or {})
    entries = meals = meals_assumed = entries_unknown = must_cost = 0
    hours_assumed = {row["place_id"] for row in items if row["hours_assumed"]}
    for row in items:
        meal = row["kind"] == "meal" or "food" in (row["category"], row["parent_category"])
        if meal:
            meals += row["est_cost_kzt"]
            meals_assumed += 1 if row["cost_assumed"] else 0
        else:
            entries += row["est_cost_kzt"]
            entries_unknown += 1 if row["cost_assumed"] else 0
        if row["is_must_have"]:
            must_cost += row["est_cost_kzt"]
    lodging_block = stored.get("lodging") or {}
    lodging = int(lodging_block.get("cost_kzt", 0))
    transport = sum(leg["cost_kzt"] for leg in legs)
    breakdown = {
        "lodging_kzt": lodging,
        "entries_kzt": entries,
        "meals_kzt": meals,
        "transport_kzt": transport,
        "events_kzt": int(stored.get("breakdown", {}).get("events_kzt", 0)),
    }
    total = sum(breakdown.values())
    budget_kzt = int(trip["budget_kzt"] or stored.get("budget_kzt") or 0)
    shortfall = max(0, total - budget_kzt)
    cheapest_night = None
    if lodging_block.get("needed"):
        options = await store.lodging_rows(conn, trip["id"])
        cheapest_night = min((o["total_kzt"] for o in options), default=None)
    floor = must_cost + (cheapest_night if cheapest_night is not None else lodging)
    stored.update(
        breakdown=breakdown,
        total_kzt=total,
        remaining_kzt=budget_kzt - total,
        shortfall_kzt=shortfall,
        status="over" if shortfall else "ok",
        must_have_cost_kzt=floor,
        must_haves_exceed_budget=floor > budget_kzt,
        variants=None,
    )
    assumptions = dict(stored.get("assumptions") or {})
    assumptions.update(meals_assumed=meals_assumed, entries_unknown=entries_unknown)
    stored["assumptions"] = assumptions
    _set_warning(warnings, "over_budget", str(shortfall) if shortfall else None)
    _set_warning(warnings, "must_haves_exceed_budget", str(floor) if floor > budget_kzt else None)
    _set_warning(warnings, "meal_prices_assumed", str(meals_assumed) if meals_assumed else None)
    # same count as the layout's warning (places without opening hours), after every edit
    _set_warning(warnings, "hours_assumed", str(len(hours_assumed)) if hours_assumed else None)
    return stored, total


async def _save_trip(
    conn,
    trip: Dict[str, Any],
    budget: Dict[str, Any],
    total: int,
    warnings: List[dict],
    unmet: List[dict],
) -> int:
    """Write the recomputed trip row, delete the stale variants, bump the version."""
    await execute(
        conn,
        "DELETE FROM trip_items WHERE trip_id = %s AND variant <> %s",
        (trip["id"], store.MAIN),
    )
    row = await fetch_one(
        conn,
        """
        UPDATE trips SET budget = %s, warnings = %s, must_have_unmet = %s, total_cost_kzt = %s,
                         version = version + 1, updated_at = now()
        WHERE id = %s RETURNING version
        """,
        (Jsonb(budget), Jsonb(warnings), Jsonb(unmet), total, trip["id"]),
    )
    return row["version"]


# --- loading ----------------------------------------------------------------------------
TRIP_CHANGED = "trip_changed"


async def _plan_trip(
    conn, user_id: UUID, trip_id: UUID, expected_version: Optional[int] = None
) -> Dict[str, Any]:
    """Phase 1: the user's trip WITHOUT a lock. `expected_version` (a proposal's plan version)
    that no longer matches is `trip_changed` too."""
    trip = await store.get_trip_row(conn, user_id, trip_id)
    if trip is None:
        raise AppError(404, "not_found")
    if expected_version is not None and trip["version"] != expected_version:
        raise AppError(409, TRIP_CHANGED)
    return trip


async def _lock_unchanged(conn, user_id: UUID, trip_id: UUID, version: int) -> Dict[str, Any]:
    """Phase 2: lock the trip row and check that it is still the version that was planned."""
    trip = await store.get_trip_row(conn, user_id, trip_id, lock=True)
    if trip is None:
        raise AppError(404, "not_found")
    if trip["version"] != version:
        raise AppError(409, TRIP_CHANGED)
    return trip


def _find_item(items: List[dict], item_id: UUID) -> dict:
    for row in items:
        if row["id"] == item_id:
            return row
    raise AppError(404, "not_found")


def _point(row: dict) -> Point:
    return (row["lat"], row["lon"])


async def _places(conn, ids: List[UUID]) -> Dict[UUID, Place]:
    rows = await fetch_all(conn, planner_sql.PLACES_BY_ID, {"ids": ids})
    return {r["id"]: place_from_row(r) for r in rows}


async def _preferences(conn, trip_id: UUID, day: date, items: List[dict]) -> Dict[Any, str]:
    """(origin point, destination point) -> mode the person has on this day's legs."""
    by_id = {r["id"]: r for r in items}
    prefs: Dict[Any, str] = {}
    for leg in await store.main_legs(conn, trip_id):
        if leg["day"] != day or not leg["chosen_mode"] or leg["from_item_id"] is None:
            continue
        origin, dest = by_id.get(leg["from_item_id"]), by_id.get(leg["to_item_id"])
        if origin and dest:
            prefs[(_point(origin), _point(dest))] = leg["chosen_mode"]
    return prefs


async def _retime(
    conn,
    router: Any,
    trip: Dict[str, Any],
    day: date,
    items: List[dict],
    stops: List[KeptStop],
    forecast: Any = None,
) -> RetimedDay:
    prefs = await _preferences(conn, trip["id"], day, items)
    hours = await hrs.load_hours(conn, [s.place.id for s in stops])
    travel, legs = await leg_tools(conn, router, trip["start_date"])
    return await retime_day(
        day,
        (trip["brief"] or {}).get("pace"),
        stops,
        hours,
        travel,
        PreferredLegs(legs, prefs),
        forecast,
    )


def _kept(row: dict, place: Place) -> KeptStop:
    return KeptStop(place, row["kind"], row["meal"], row["is_must_have"])


async def _day_stops(conn, items: List[dict], day: date) -> Tuple[List[dict], Dict[UUID, Place]]:
    rows = [r for r in items if r["day"] == day]
    places = await _places(conn, [r["place_id"] for r in rows])
    return rows, places


def _name(row: dict, locale: str) -> str:
    return service.pick_text(row, "name", locale)[0] or ""


async def _signal(conn, user_id: UUID, trip_id: UUID, row: dict, signal: str) -> None:
    await execute(
        conn,
        "INSERT INTO user_place_signals (user_id, place_id, category_slug, signal, trip_id) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, row["place_id"], row["category"], signal, trip_id),
    )


def _apply_retime(
    result: RetimedDay, day: date, warnings: List[dict], unmet: List[dict], locale: str
) -> List[Dict[str, Any]]:
    """Fold the re-timing's warnings and dropped stops into the trip's lists; returns the
    dropped stops for the response."""
    warnings[:] = [
        w
        for w in warnings
        if not (w["code"] == "meal_missing" and w.get("date") == day.isoformat())
    ]
    for w in result.warnings:
        warnings.append(
            {"code": w.code, "date": w.date.isoformat() if w.date else None, "detail": w.detail}
        )
    if result.travel_estimated and not any(w["code"] == "travel_estimated" for w in warnings):
        warnings.append({"code": "travel_estimated", "date": None, "detail": None})
    dropped = []
    for item in result.unplaced:
        name = item.place.name_ru if locale == "ru" else item.place.name_en
        name = name or item.place.name
        dropped.append(
            {
                "place": {"id": str(item.place.id), "name": name},
                "reason": item.reason,
                "must_have": item.must_have,
            }
        )
        if item.must_have:
            unmet.append({"wish": None, "place_name": name, "reason": item.reason})
    return dropped


def _result(
    trip_id: UUID, version: int, action: str, day: date, budget: Dict[str, Any], **extra: Any
) -> Dict[str, Any]:
    out = {
        "trip_id": str(trip_id),
        "version": version,
        "action": action,
        "changed_days": [day.isoformat()],
        "budget": budget_summary(budget),
    }
    out.update(extra)
    return out


# --- remove -----------------------------------------------------------------------------
async def remove_item(
    conn,
    router: Any,
    user_id: UUID,
    trip_id: UUID,
    item_id: UUID,
    locale: str,
    force: bool = False,
    expected_version: Optional[int] = None,
) -> Dict[str, Any]:
    """Remove a stop and re-time its day. Raises 404 (foreign / missing trip or item), 409
    `must_have` (a must-have without `force`) and 409 `trip_changed` (see the module doc)."""
    trip = await _plan_trip(conn, user_id, trip_id, expected_version)
    items = await store.main_items(conn, trip_id)
    target = _find_item(items, item_id)
    if target["is_must_have"] and not force:
        raise AppError(409, "must_have")
    day = target["day"]
    rows, places = await _day_stops(conn, items, day)
    stops = [_kept(r, places[r["place_id"]]) for r in rows if r["id"] != item_id]
    result = await _retime(conn, router, trip, day, items, stops)

    trip = await _lock_unchanged(conn, user_id, trip_id, trip["version"])
    await store.replace_day(conn, trip_id, day, result.plan)
    warnings, unmet = list(trip["warnings"]), list(trip["must_have_unmet"])
    if target["is_must_have"]:
        unmet.append(
            {"wish": None, "place_name": _name(target, locale), "reason": MUST_HAVE_UNMET_REMOVED}
        )
    dropped = _apply_retime(result, day, warnings, unmet, locale)
    budget, total = await recompute_budget(conn, trip, warnings)
    version = await _save_trip(conn, trip, budget, total, warnings, unmet)
    await _signal(conn, user_id, trip_id, target, "removed")
    return _result(
        trip_id, version, "remove", day, budget,
        removed={"item_id": str(item_id), "place": read.place_ref(target, locale)},
        dropped=dropped,
    )  # fmt: skip


# --- replace ----------------------------------------------------------------------------
def _lodging(place: Place) -> bool:
    return "accommodation" in (place.kind, place.category, place.parent)


def _usable(place: Place, meal: bool) -> bool:
    if meal:
        return place.is_food and place.category not in NON_MEAL_CATEGORIES
    return True


async def _candidates(
    conn,
    old: dict,
    taken: set,
    place_id: Optional[UUID],
    category: Optional[str],
    query: Optional[str],
) -> List[Place]:
    """Replacement candidates, best first. Active non-accommodation places only; a place that
    is already in the trip is never a candidate."""
    west, south, east, north = ALMATY_BBOX
    area = {"west": west, "south": south, "east": east, "north": north}
    if place_id is not None:
        active = await fetch_one(
            conn, "SELECT 1 AS ok FROM places WHERE id = %s AND status = 'active'", (place_id,)
        )
        found = [
            p for p in (await _places(conn, [place_id])).values()
            if active and not _lodging(p)
        ]  # fmt: skip
    elif category:
        rows = await fetch_all(
            conn, planner_sql.MUST_HAVE_BY_CATEGORY,
            dict(area, slugs=[category], limit=CANDIDATE_POOL),
        )  # fmt: skip
        found = [place_from_row(r) for r in rows]
        here = _point(old)
        ranked = sorted(
            enumerate(found),
            key=lambda ip: (
                haversine_m(here, (ip[1].lat, ip[1].lon)) / 1000.0 + 0.1 * ip[0],
                ip[0],
            ),
        )  # nearest to the place it replaces, the more popular first on ties
        found = [p for _, p in ranked]
    else:
        text = " ".join((query or "").split())
        rows = await fetch_all(
            conn, planner_sql.MUST_HAVE_BY_NAME,
            dict(area, q=text, pattern=service.like_pattern(text), limit=CANDIDATE_POOL),
        )  # fmt: skip
        found = [place_from_row(r) for r in rows]
    return [p for p in found if p.id not in taken]


MAX_ALTERNATIVES = 5


async def alternatives(
    conn, user_id: UUID, trip_id: UUID, item_id: UUID, locale: str
) -> Dict[str, Any]:
    """Up to 5 places similar to a stop (same category, nearest first), none already in the trip
    (Ш-55, for the replace UI). Read-only; replacing is `replace_item` with `place_id`; whether
    one fits the day is only known when it is tried, so a pick may still answer 409."""
    if await store.get_trip_row(conn, user_id, trip_id) is None:
        raise AppError(404, "not_found")
    items = await store.main_items(conn, trip_id)
    target = _find_item(items, item_id)
    if not target["category"]:
        return {"items": []}
    taken = {r["place_id"] for r in items}
    meal = target["kind"] == "meal"
    found = [
        p for p in await _candidates(conn, target, taken, None, target["category"], None)
        if _usable(p, meal)
    ][:MAX_ALTERNATIVES]  # fmt: skip
    here = _point(target)
    out = []
    for place in found:
        price = place.avg_check_kzt if place.is_food else place.entry_price_kzt
        out.append(
            {
                "id": str(place.id),
                "name": (place.name_ru if locale == "ru" else place.name_en)
                or place.name_ru
                or place.name_en
                or "",
                "category": place.category,
                "lat": place.lat,
                "lon": place.lon,
                "price_kzt": int(price) if price is not None else None,
                "distance_m": int(round(haversine_m(here, (place.lat, place.lon)))),
            }
        )
    return {"items": out}


async def first_fit_replacement(
    conn,
    router: Any,
    trip: Dict[str, Any],
    items: List[dict],
    target: dict,
    rows: List[dict],
    places: Dict[UUID, Place],
    candidates: List[Place],
    forecast: Any = None,
) -> Optional[Tuple[Place, RetimedDay]]:
    """The first candidate that takes the target's place in its day without pushing a stop out
    (at most MAX_REPLACEMENT_TRIES are tried); read-only. None when nothing fits."""
    for cand in candidates[:MAX_REPLACEMENT_TRIES]:
        stops = [
            KeptStop(cand, target["kind"], target["meal"], False)
            if r["id"] == target["id"]
            else _kept(r, places[r["place_id"]])
            for r in rows
        ]
        result = await _retime(conn, router, trip, target["day"], items, stops, forecast)
        if not result.unplaced and any(s.place.id == cand.id for s in result.plan.stops):
            return cand, result
    return None


async def replace_item(
    conn,
    router: Any,
    user_id: UUID,
    trip_id: UUID,
    item_id: UUID,
    locale: str,
    place_id: Optional[UUID] = None,
    category: Optional[str] = None,
    query: Optional[str] = None,
    force: bool = False,
    forecast: Any = None,
    record_signal: bool = True,
    expected_version: Optional[int] = None,
) -> Dict[str, Any]:
    """Replace a stop with another place (by id, category slug or name) in the same position of
    the same day. The first candidate that fits the day without pushing anything out is used;
    409 `no_replacement` when none does, 409 `must_have` for a must-have without `force`, 409
    `trip_changed` (see the module doc)."""
    if sum(x is not None and x != "" for x in (place_id, category, query)) != 1:
        raise AppError(422, "validation_error", "Give exactly one of place_id, category, query")
    trip = await _plan_trip(conn, user_id, trip_id, expected_version)
    items = await store.main_items(conn, trip_id)
    target = _find_item(items, item_id)
    if target["is_must_have"] and not force:
        raise AppError(409, "must_have")
    day = target["day"]
    rows, places = await _day_stops(conn, items, day)
    taken = {r["place_id"] for r in items}
    meal = target["kind"] == "meal"
    candidates = [
        p for p in await _candidates(conn, target, taken, place_id, category, query)
        if _usable(p, meal)
    ]  # fmt: skip
    chosen = await first_fit_replacement(
        conn, router, trip, items, target, rows, places, candidates, forecast
    )
    if chosen is None:
        raise AppError(409, "no_replacement")
    new_place, result = chosen

    trip = await _lock_unchanged(conn, user_id, trip_id, trip["version"])
    item_ids = await store.replace_day(conn, trip_id, day, result.plan)
    warnings, unmet = list(trip["warnings"]), list(trip["must_have_unmet"])
    if target["is_must_have"]:
        unmet.append(
            {"wish": None, "place_name": _name(target, locale), "reason": MUST_HAVE_UNMET_REPLACED}
        )
    dropped = _apply_retime(result, day, warnings, unmet, locale)
    budget, total = await recompute_budget(conn, trip, warnings)
    version = await _save_trip(conn, trip, budget, total, warnings, unmet)
    if record_signal:  # a weather swap (Ш-40) says nothing about the person's taste
        await _signal(conn, user_id, trip_id, target, "replaced")
    name = new_place.name_ru if locale == "ru" else new_place.name_en
    return _result(
        trip_id, version, "replace", day, budget,
        replaced={"item_id": str(item_id), "place": read.place_ref(target, locale)},
        replacement={
            "item_id": str(item_ids[new_place.id]),
            "place": {
                "id": str(new_place.id),
                "name": name or new_place.name,
                "category": new_place.category,
                "lat": new_place.lat,
                "lon": new_place.lon,
            },
        },
        dropped=dropped,
    )  # fmt: skip


# --- move a stop to another day (Ш-40 weather proposals) ---------------------------------
async def plan_move(
    conn,
    router: Any,
    trip: Dict[str, Any],
    items: List[dict],
    target: dict,
    to_day: date,
    forecast: Any = None,
) -> Tuple[RetimedDay, RetimedDay]:
    """Read-only: the two days after `target` leaves its day and goes to the END of `to_day`
    (both re-timed). The caller checks `unplaced` and that the stop is in the second plan."""
    day = target["day"]
    rows, places = await _day_stops(conn, items, day)
    moved = places[target["place_id"]]
    stops_from = [_kept(r, places[r["place_id"]]) for r in rows if r["id"] != target["id"]]
    rows_to, places_to = await _day_stops(conn, items, to_day)
    stops_to = [_kept(r, places_to[r["place_id"]]) for r in rows_to]
    stops_to.append(KeptStop(moved, target["kind"], target["meal"], target["is_must_have"]))
    result_from = await _retime(conn, router, trip, day, items, stops_from, forecast)
    result_to = await _retime(conn, router, trip, to_day, items, stops_to, forecast)
    return result_from, result_to


def move_fits(target: dict, result_from: RetimedDay, result_to: RetimedDay) -> bool:
    return (
        not result_from.unplaced
        and not result_to.unplaced
        and any(s.place.id == target["place_id"] for s in result_to.plan.stops)
    )


async def move_item(
    conn,
    router: Any,
    user_id: UUID,
    trip_id: UUID,
    item_id: UUID,
    to_day: date,
    locale: str,
    forecast: Any = None,
    expected_version: Optional[int] = None,
) -> Dict[str, Any]:
    """Move a stop to the end of another day of the trip and re-time both days.

    404 for a foreign / missing trip or item, 422 when `to_day` is outside the trip or the same
    day, 409 `proposal_not_applicable` when the stop no longer fits there, 409 `trip_changed`
    (see the module doc). No memory signal: the move is not a statement of taste.
    """
    trip = await _plan_trip(conn, user_id, trip_id, expected_version)
    items = await store.main_items(conn, trip_id)
    target = _find_item(items, item_id)
    if to_day == target["day"] or not trip["start_date"] <= to_day <= trip["end_date"]:
        raise AppError(422, "validation_error", "to_day must be another day of the trip")
    result_from, result_to = await plan_move(conn, router, trip, items, target, to_day, forecast)
    if not move_fits(target, result_from, result_to):
        raise AppError(409, "proposal_not_applicable")
    trip = await _lock_unchanged(conn, user_id, trip_id, trip["version"])
    day = target["day"]
    await store.replace_day(conn, trip_id, day, result_from.plan)
    new_ids = await store.replace_day(conn, trip_id, to_day, result_to.plan)
    warnings, unmet = list(trip["warnings"]), list(trip["must_have_unmet"])
    _apply_retime(result_from, day, warnings, unmet, locale)
    _apply_retime(result_to, to_day, warnings, unmet, locale)
    budget, total = await recompute_budget(conn, trip, warnings)
    version = await _save_trip(conn, trip, budget, total, warnings, unmet)
    return {
        "trip_id": str(trip_id),
        "version": version,
        "action": "move",
        "changed_days": [day.isoformat(), to_day.isoformat()],
        "budget": budget_summary(budget),
        "moved": {"item_id": str(new_ids[target["place_id"]]), "from_day": day.isoformat(),
                  "to_day": to_day.isoformat()},
    }  # fmt: skip


# --- transport mode of a leg --------------------------------------------------------------
def _option_of(options: List[dict], mode: str, variant: int) -> Optional[dict]:
    return next((o for o in options if o["mode"] == mode and o.get("variant", 0) == variant), None)


async def _fetch_variant(
    conn, router: Any, trip: Dict[str, Any], leg: dict, mode: str, variant: int
) -> Optional[dict]:
    """Phase 1 of a choice of a path variant the plan did not store (the planner keeps only
    variant 0 per mode): ask the router for the leg's alternatives (Ш-22a) at its departure time
    and return the stored form of the one asked for, or None when there is no such variant."""
    items = await store.main_items(conn, trip["id"])
    by_id = {r["id"]: r for r in items}
    destination = by_id[leg["to_item_id"]]
    origin = by_id.get(leg["from_item_id"]) if leg["from_item_id"] else None
    start = _point(origin) if origin else ALMATY_CENTRE  # the day's start point (no lodging yet)
    _, legs = await leg_tools(conn, router, trip["start_date"])
    try:
        options = await get_directions(
            legs.router, legs.network, legs.tariffs, start, _point(destination), leg["depart_at"]
        )
    except RoutingUnavailable:
        raise AppError(503, "routing_unavailable") from None
    found = next((o for o in options if o.mode == mode and o.variant == variant), None)
    return found.model_dump(exclude_none=True, exclude={"steps"}) if found else None


async def set_leg_mode(
    conn,
    user_id: UUID,
    trip_id: UUID,
    leg_id: UUID,
    mode: str,
    variant: Optional[int] = None,
    router: Any = None,
) -> Dict[str, Any]:
    """The person picks one of the leg's transport options (and, optionally, one of its path
    variants, Ш-22a: `variant`, default 0 = the optimal one).

    The leg's chosen mode and variant, cost (the option's upper cost) and reserved travel time
    follow the option; the trip's transport cost and total are recomputed and `version` grows (the
    plan the client may have saved offline is now different). A variant the plan does not hold
    (the planner stores variant 0 per mode) is asked from the router BEFORE the trip is locked
    and added to the leg's `options`. The day is NOT re-timed: stops keep their times, so a slower
    option can arrive after the next stop starts: `late_by_s` > 0 says by how much (and the leg
    shows the same number in `GET /trips/{id}`). The next re-timing of the day (an edit) honours
    the mode but goes back to variant 0.
    422 `validation_error` when the leg has no such option, 404 for a foreign / missing trip or
    leg, 409 `trip_changed` (see the module doc).
    """
    trip = await _plan_trip(conn, user_id, trip_id)
    legs = await store.main_legs(conn, trip_id)
    leg = next((row for row in legs if row["id"] == leg_id), None)
    if leg is None:
        raise AppError(404, "not_found")
    wanted = variant or 0
    option = _option_of(leg["options"], mode, wanted)
    added = False
    if option is None and wanted > 0 and router is not None:
        option = await _fetch_variant(conn, router, trip, leg, mode, wanted)
        added = option is not None
    if option is None:
        raise AppError(
            422, "validation_error", "This leg has no %r option, variant %d" % (mode, wanted)
        )
    travel_s = int(round(option.get("duration_s_max") or option["duration_s"]))

    trip = await _lock_unchanged(conn, user_id, trip_id, trip["version"])
    options = list(leg["options"]) + ([option] if added else [])
    await execute(
        conn,
        "UPDATE trip_legs SET chosen_mode = %s, chosen_variant = %s, cost_kzt = %s, travel_s = %s,"
        " options = %s WHERE id = %s",
        (mode, wanted, int(option["cost_kzt_max"]), travel_s, Jsonb(options), leg_id),
    )
    warnings, unmet = list(trip["warnings"]), list(trip["must_have_unmet"])
    budget, total = await recompute_budget(conn, trip, warnings)
    version = await _save_trip(conn, trip, budget, total, warnings, unmet)

    leg.update(
        chosen_mode=mode, chosen_variant=wanted, cost_kzt=int(option["cost_kzt_max"]),
        travel_s=travel_s, options=options,
    )  # fmt: skip
    destination = next(
        r for r in await store.main_items(conn, trip_id) if r["id"] == leg["to_item_id"]
    )
    arrives = leg["depart_at"] + timedelta(seconds=travel_s)
    late = read.leg_late_by_s(leg, destination["starts_at"])
    return {
        "trip_id": str(trip_id),
        "version": version,
        "leg": read.leg_json(leg, destination["starts_at"]),
        "arrives_at": read.local(arrives),
        "late_by_s": late,
        "changed_days": [leg["day"].isoformat()],
        "budget": budget_summary(budget),
    }
