"""Ш-36: from a brief to a complete plan, in memory (no writes).

candidates (Ш-33) -> layout (Ш-34) -> lodging and budget (Ш-35). `app.trips.store` persists the
result and `app.chat.build_tool` turns it into the `route_ready` event and the tool result.
Deterministic for a given brief, database and router answers.

Reads take one short transaction; the router (Valhalla) is called with no connection held.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence
from uuid import UUID

from app.crowd.service import ProfileCrowd
from app.db import fetch_all
from app.memory.affinity import NO_MEMORY, load_memory
from app.planner import budget as bud
from app.planner import hours as hrs
from app.planner import sql
from app.planner.area import ALMATY_BBOX
from app.planner.candidates import Selection, select_candidates
from app.planner.events import load_event_index
from app.planner.layout import TripLayout, plan_days
from app.planner.model import Place
from app.planner.travel import DirectionsLegs, RouterMatrix
from app.planner.weather import Forecast, UnknownForecast
from app.routing import get_network
from app.routing.base import RoutingProvider
from app.routing.costs import load_tariffs

log = logging.getLogger(__name__)


@dataclass
class BuiltPlan:
    brief: Mapping[str, Any]
    selection: Selection
    layout: TripLayout
    lodging: bud.LodgingPlan
    costs: bud.Costs
    budget_kzt: int
    must_have_floor_kzt: int
    variants: List[bud.Variant] = field(default_factory=list)

    @property
    def over_budget(self) -> bool:
        return self.costs.total > self.budget_kzt

    @property
    def shortfall_kzt(self) -> int:
        return max(0, self.costs.total - self.budget_kzt)

    @property
    def must_haves_exceed_budget(self) -> bool:
        return self.must_have_floor_kzt > self.budget_kzt


def trip_dates(brief: Mapping[str, Any]) -> List[date]:
    start, end = brief["start_date"], brief["end_date"]
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


async def leg_tools(conn, router: RoutingProvider, first_day: date):
    """(travel matrix, leg option builder) for planning; shared by `build_plan` and trip edits.

    Reads tariffs and the transit network on `conn`; the router is called later, by the caller,
    with whatever connection state it likes.
    """
    tariffs = await load_tariffs(conn, first_day)
    network = None
    if "bus" in tariffs or "metro" in tariffs:
        network = await get_network(conn)
    return RouterMatrix(router), DirectionsLegs(router, network, tariffs)


async def build_plan(
    db,
    brief: Mapping[str, Any],
    router: RoutingProvider,
    forecast: Optional[Forecast] = None,
    user_id: Optional[UUID] = None,
    chosen_places: Optional[Mapping[str, UUID]] = None,
) -> BuiltPlan:
    """Plan the whole trip for a complete brief (dates and budget set).

    `forecast`: the planner's weather view (`providers.weather.city_forecast`); default none.
    `user_id`: the signed-in owner; their memory (rejected categories, favourites, Ш-41) shapes
    the scores. None = no memory. `chosen_places`: places picked on the chat's live route per
    must-have wish (Ш-54, see `select_candidates`).
    """
    dates = trip_dates(brief)
    west, south, east, north = ALMATY_BBOX
    area = {"west": west, "south": south, "east": east, "north": north}
    async with db.transaction() as conn:
        memory = await load_memory(conn, user_id) if user_id else NO_MEMORY
        crowd = await ProfileCrowd.load(conn)  # Ш-47: own crowd data; unknown below its threshold
        events = await load_event_index(conn, brief)  # Ш-48: events of the trip dates
        selection = await select_candidates(
            conn, brief, memory=memory.penalties, favorites=memory, crowd=crowd,
            event_bonus=events.bonus, chosen_places=chosen_places,
        )  # fmt: skip
        selection.events = events.items
        must = selection.must_have_places
        acts = [c.place for c in selection.activities]
        food = [c.place for c in selection.food]
        hours = await hrs.load_hours(conn, [p.id for p in must + acts + food])
        travel, legs = await leg_tools(conn, router, dates[0])
        lodging_rows = (
            await fetch_all(conn, sql.LODGING, area) if brief.get("has_accommodation") is not True
            else []
        )  # fmt: skip

    forecast = forecast or UnknownForecast()  # Ш-39: `city_forecast`, not wired in yet (Ш-40)
    pace = brief.get("pace")

    async def replan(activities: Sequence[Place], meals: Sequence[Place]) -> TripLayout:
        return await plan_days(dates, pace, must, activities, meals, hours, travel, legs, forecast)

    layout = await replan(acts, food)
    nights = bud.trip_nights(brief["start_date"], brief["end_date"])
    lodging = bud.choose_lodging(
        [bud.lodging_from_row(r) for r in lodging_rows],
        bud.layout_centre(layout),
        nights,
        needed=brief.get("has_accommodation") is not True,
    )
    costs = bud.plan_costs(layout, lodging.cost())
    plan = BuiltPlan(
        brief=brief, selection=selection, layout=layout, lodging=lodging, costs=costs,
        budget_kzt=int(brief["budget_kzt"]),
        must_have_floor_kzt=bud.must_have_floor(layout, lodging),
    )  # fmt: skip
    if plan.over_budget:
        inputs = bud.PlanInputs(
            activities=acts,
            food=food,
            scores={c.place.id: c.score.total for c in selection.activities + selection.food},
            replan=replan,
        )
        plan.variants = [
            await bud.drop_variant(inputs, layout, lodging, plan.budget_kzt),
            await bud.cheaper_variant(inputs, layout, lodging, plan.budget_kzt),
        ]
    return plan


# --- public shapes ----------------------------------------------------------------------
def place_name(place: Any, locale: str) -> str:
    order = (place.name_ru, place.name_en) if locale == "ru" else (place.name_en, place.name_ru)
    return next((n for n in order if n), "")


def _ref(place: Any, locale: str) -> Dict[str, Any]:
    return {"place_id": str(place.id), "name": place_name(place, locale)}


def _breakdown(costs: bud.Costs) -> Dict[str, int]:
    return {
        "lodging_kzt": costs.lodging,
        "entries_kzt": costs.entries,
        "meals_kzt": costs.meals,
        "transport_kzt": costs.transport,
        "events_kzt": costs.events,
    }


def _lodging_json(plan: bud.LodgingPlan, locale: str, with_options: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "needed": plan.needed,
        "nights": plan.nights,
        "cost_kzt": plan.cost(),
        "price_assumed": plan.price_assumed,
    }
    if with_options:
        out["options"] = [
            {
                "place_id": str(o.place.id),
                "name": place_name(o.place, locale),
                "category": o.place.category,
                "lat": o.place.lat,
                "lon": o.place.lon,
                "price_per_night_kzt": o.price,
                "price_assumed": o.assumed,
                "total_kzt": o.total,
                "distance_km": round(o.distance_km, 1),
                "recommended": o.recommended,
            }
            for o in plan.options
        ]
    return out


def _variant_json(
    plan: BuiltPlan, variant: bud.Variant, locale: str, with_places: bool
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "feasible": variant.costs.total <= plan.budget_kzt,
        "total_kzt": variant.costs.total,
        "saves_kzt": plan.costs.total - variant.costs.total,
        "shortfall_kzt": max(0, variant.costs.total - plan.budget_kzt),
        "breakdown": _breakdown(variant.costs),
    }
    if variant.kind == "drop_places":
        out["removed_count"] = len(variant.removed)
        if with_places:
            out["removed"] = [_ref(p, locale) for p in variant.removed]
    else:
        out["swaps_count"] = len(variant.swaps)
        out["lodging_changed"] = (
            variant.lodging is not None and variant.lodging is not plan.lodging.recommended
        )
        out["lodging_total_kzt"] = plan.lodging.cost(variant.lodging)
        if with_places:
            out["swaps"] = [
                {"from": _ref(a, locale), "to": _ref(b, locale)} for a, b in variant.swaps
            ]
            out["lodging"] = (
                dict(_ref(variant.lodging.place, locale), total_kzt=variant.lodging.total)
                if out["lodging_changed"] and variant.lodging
                else None
            )
    return out


def budget_json(plan: BuiltPlan, locale: str, with_places: bool = True) -> Dict[str, Any]:
    """The budget block of `route_ready`. `with_places=False` is what `trips.budget` stores:
    no place ids (they would go stale when places are merged), only numbers and counts."""
    costs = plan.costs
    out: Dict[str, Any] = {
        "budget_kzt": plan.budget_kzt,
        "status": "over" if plan.over_budget else "ok",
        "total_kzt": costs.total,
        "remaining_kzt": plan.budget_kzt - costs.total,
        "shortfall_kzt": plan.shortfall_kzt,
        "breakdown": _breakdown(costs),
        "assumptions": {
            "meals_assumed": costs.meals_assumed,
            "entries_unknown": costs.entries_unknown,
            "lodging_price_assumed": plan.lodging.price_assumed,
        },
        "must_have_cost_kzt": plan.must_have_floor_kzt,
        "must_haves_exceed_budget": plan.must_haves_exceed_budget,
        "lodging": _lodging_json(plan.lodging, locale, with_places),
        "variants": (
            {v.kind: _variant_json(plan, v, locale, with_places) for v in plan.variants}
            if plan.variants
            else None
        ),
        "choice": None,
    }
    return out


def warnings_json(plan: BuiltPlan) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = [
        {"code": w.code, "date": w.date.isoformat() if w.date else None, "detail": w.detail}
        for w in plan.layout.warnings
    ]

    def add(code: str, detail: Optional[str] = None) -> None:
        out.append({"code": code, "date": None, "detail": detail})

    if plan.over_budget:
        add("over_budget", str(plan.shortfall_kzt))
    if plan.must_haves_exceed_budget:
        add("must_haves_exceed_budget", str(plan.must_have_floor_kzt))
    if plan.costs.meals_assumed:
        add("meal_prices_assumed", str(plan.costs.meals_assumed))
    if plan.lodging.price_assumed:
        add("lodging_price_assumed")
    if plan.lodging.no_options:
        add("no_lodging_found")
    return out


def must_have_unmet_json(plan: BuiltPlan, locale: str) -> List[Dict[str, Any]]:
    """Wishes the plan does not honour (SSOT §16.11): nothing found, outside the v1 area (Ш-56),
    or found but no room."""
    out: List[Dict[str, Any]] = []
    for wish in plan.selection.must_haves:
        if wish.places:
            continue
        if wish.outside is not None:
            out.append({
                "wish": wish.text, "place_name": wish.outside.name(locale),
                "reason": "outside_area", "outside_area": wish.outside.as_json(locale),
            })  # fmt: skip
        else:
            out.append({"wish": wish.text, "place_name": None, "reason": "no_place"})
    for item in plan.layout.must_have_unplaced:
        out.append(
            {"wish": None, "place_name": place_name(item.place, locale), "reason": item.reason}
        )
    return out
