"""Ш-36: from a brief to a complete plan, in memory (no writes).

candidates (Ш-33) -> layout (Ш-34) -> lodging and budget (Ш-35). `app.trips.store` persists the
result and `app.chat.build_tool` turns it into the `route_ready` event and the tool result.
Deterministic for a given brief, database and router answers.

Reads take one short transaction; the router (Valhalla) is called with no connection held.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID

from app.crowd.service import ProfileCrowd
from app.db import fetch_all
from app.memory.affinity import NO_MEMORY, load_memory
from app.planner import budget as bud
from app.planner import country as ctry
from app.planner import hours as hrs
from app.planner import scoring, sql
from app.planner.candidates import Selection, select_candidates
from app.planner.events import load_event_index
from app.planner.layout import DAY_END, DAY_START, LayoutWarning, TripLayout, Unplaced, plan_days
from app.planner.model import Place
from app.planner.outside import outside_wish
from app.planner.travel import DirectionsLegs, RouterMatrix
from app.planner.weather import Forecast, UnknownForecast
from app.regions import default_region
from app.routing import get_network
from app.routing.base import Point, RoutingProvider
from app.routing.costs import load_intercity_params, load_tariffs

log = logging.getLogger(__name__)


@dataclass
class StayPlan:
    """Ш-61: a night spot away from the home city (Saty, Turkistan): where, how many nights, and
    the lodging options counted for them (SSOT §5.2: nights x price per night)."""

    index: int  # 1.. in the order of the trip; 0 is the home city
    city: Dict[str, str]  # {ru, en}
    region: str
    point: Point
    nights: int
    lodging: bud.LodgingPlan


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
    stays: List[StayPlan] = field(default_factory=list)

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


def _drop_far_wishes(selection: Selection, far_ids: set) -> None:
    """The country settings are not loaded: a place far from the city cannot be planned, so its
    wish is reported as outside the area (as before Ш-61) instead of being put in a city day."""
    for wish in selection.must_haves:
        if any(p.id in far_ids for p in wish.places):
            wish.places, wish.how, wish.outside = [], "outside", outside_wish(wish.text)


def _home_json(label: Dict[str, str]) -> Dict[str, Any]:
    region = default_region()
    lat, lon = region.centre
    return {"city": dict(label), "region": region.id, "lat": lat, "lon": lon}


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

    Ш-61: wishes far from the home city (Charyn, Kolsai, Turkistan) are planned by
    `planner.country` (outings, nights near the place, transfers between cities); the days that
    stay are the home city's, laid out by `plan_days` as before. A trip with no far wish and no
    dated wish takes exactly the path it took before.
    """
    dates = trip_dates(brief)
    region = default_region()
    west, south, east, north = region.bbox
    area = {"west": west, "south": south, "east": east, "north": north}
    home_label = {"ru": region.name_ru, "en": region.name_en}
    async with db.transaction() as conn:
        memory = await load_memory(conn, user_id) if user_id else NO_MEMORY
        crowd = await ProfileCrowd.load(conn)  # Ш-47: own crowd data; unknown below its threshold
        events = await load_event_index(conn, brief)  # Ш-48: events of the trip dates
        selection = await select_candidates(
            conn, brief, memory=memory.penalties, favorites=memory, crowd=crowd,
            event_bonus=events.bonus, chosen_places=chosen_places,
        )  # fmt: skip
        selection.events = events.items
        settings = await ctry.load_settings(conn)
        params = await load_intercity_params(conn)
        wishes = ctry.wish_places(brief, selection)
        far: List[ctry.WishPlace] = []
        if settings is not None and params is not None:
            _, far = ctry.split_local_far(wishes, region.centre, settings.local_radius_km)
        else:  # no country settings: only places inside the home region are planned
            stray = {x.place.id for x in wishes if not region.contains(x.place.lat, x.place.lon)}
            _drop_far_wishes(selection, stray)
            wishes = [x for x in wishes if x.place.id not in stray]
        far_ids = {x.place.id for x in far}
        must = [p for p in selection.must_have_places if p.id not in far_ids]
        far_places = [p for p in selection.must_have_places if p.id in far_ids]
        acts = [c.place for c in selection.activities]
        food = [c.place for c in selection.food]
        hours = await hrs.load_hours(conn, [p.id for p in must + far_places + acts + food])
        travel, legs = await leg_tools(conn, router, dates[0])
        lodging_rows = (
            await fetch_all(conn, sql.LODGING, area) if brief.get("has_accommodation") is not True
            else []
        )  # fmt: skip

    forecast = forecast or UnknownForecast()  # Ш-39: `city_forecast`, not wired in yet (Ш-40)
    pace = brief.get("pace")
    pinned: Dict[UUID, date] = {}
    warnings: List[LayoutWarning] = []
    for x in wishes:
        if x.on is None or x.place.id in far_ids:
            continue
        if x.on in dates:
            pinned[x.place.id] = x.on
        else:
            warnings.append(LayoutWarning("dated_wish_out_of_range", x.on, x.place.name))

    country: Optional[ctry.CountryResult] = None
    stay_inputs: List[Tuple[Dict[str, Any], int, List[Dict[str, Any]]]] = []
    if far:
        assert settings is not None and params is not None
        pace_key = pace if pace in DAY_START else scoring.DEFAULT_PACE
        async with db.transaction() as conn:
            world = ctry.World(
                conn=conn, router=router, tariffs=legs.tariffs, params=params, legs=legs,
                settings=settings, hours=hours, dates=dates, start_min=DAY_START[pace_key],
                end_min=DAY_END[pace_key], cap=scoring.ACTIVITIES_PER_DAY[pace_key],
                budget_kzt=int(brief["budget_kzt"]), home=region.centre, home_label=home_label,
                home_region=region.id,
            )  # fmt: skip
            country = await ctry.plan_country(world, far)
            stay_inputs = await _stay_inputs(world, country, len(dates))

    def compose(home: TripLayout) -> TripLayout:
        """The home city's layout plus the far days, in date order."""
        if country is None:
            return home
        days: List[Any] = [None] * len(dates)
        for local_i, index in enumerate(country.home_indices):
            days[index] = home.days[local_i]
        for index, plan in country.days.items():
            days[index] = plan
        out = TripLayout(
            days=days, unplaced=home.unplaced + country.unplaced,
            warnings=home.warnings + country.warnings + warnings,
            start_point=home.start_point, start_point_default=home.start_point_default,
            travel_estimated=home.travel_estimated or country.estimated,
        )  # fmt: skip
        if country.estimated and not home.travel_estimated:
            out.warnings.append(LayoutWarning("travel_estimated"))
        return out

    home_dates = dates if country is None else [dates[i] for i in country.home_indices]

    async def replan(activities: Sequence[Place], meals: Sequence[Place]) -> TripLayout:
        if not home_dates:  # every day is taken by the far part: the city's wishes are not placed
            home = TripLayout(days=[])
            home.unplaced = [Unplaced(p, "no_time", True) for p in must]
        else:
            home = await plan_days(
                home_dates, pace, must, activities, meals, hours, travel, legs, forecast,
                pinned=pinned or None,
            )  # fmt: skip
        if country is None:
            home.warnings += warnings
        return compose(home)

    layout = await replan(acts, food)
    home_nights, stays = _nights(
        layout, country, stay_inputs, bud.trip_nights(brief["start_date"], brief["end_date"])
    )
    lodging = bud.choose_lodging(
        [bud.lodging_from_row(r) for r in lodging_rows],
        bud.layout_centre(_home_part(layout, country)),
        home_nights,
        needed=brief.get("has_accommodation") is not True,
    )
    lodging.extra_kzt = sum(st.lodging.cost() for st in stays)
    lodging.extra_assumed = any(st.lodging.price_assumed for st in stays)
    lodging.extra_no_options = any(st.lodging.no_options for st in stays)
    _annotate(layout, country, stays, home_label)
    costs = bud.plan_costs(layout, lodging.cost())
    plan = BuiltPlan(
        brief=brief, selection=selection, layout=layout, lodging=lodging, costs=costs,
        budget_kzt=int(brief["budget_kzt"]),
        must_have_floor_kzt=bud.must_have_floor(layout, lodging), stays=stays,
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
        for variant in plan.variants:
            _annotate(variant.layout, country, stays, home_label)
    return plan


def _home_part(layout: TripLayout, country: Optional[ctry.CountryResult]) -> TripLayout:
    """The home city's days only (the lodging of the home city is chosen near them)."""
    if country is None:
        return layout
    home = TripLayout(days=[d for i, d in enumerate(layout.days) if i in country.home_indices])
    home.start_point = layout.start_point
    return home


async def _stay_inputs(
    world: ctry.World, country: ctry.CountryResult, n: int
) -> List[Tuple[Dict[str, Any], int, List[Dict[str, Any]]]]:
    """For every night spent away from home: (overnight json, index of the first night, the lodging
    rows near the place). One entry per distinct city (the nights are counted in `_nights`)."""
    out: List[Tuple[Dict[str, Any], int, List[Dict[str, Any]]]] = []
    seen: set = set()
    for index in range(n - 1):
        sleep = country.sleeps.get(index)
        if sleep is None or index in country.transit_nights:
            continue
        key = sleep.label["ru"]
        if key in seen:
            continue
        seen.add(key)
        rows = await fetch_all(
            world.conn,
            sql.LODGING_NEAR,
            {"lat": sleep.point[0], "lon": sleep.point[1],
             "radius_m": world.settings.stay_search_km * 1000},
        )  # fmt: skip
        out.append((country.overnights[index], index, rows))  # type: ignore[arg-type]
    return out


def _nights(
    layout: TripLayout,
    country: Optional[ctry.CountryResult],
    stay_inputs: List[Tuple[Dict[str, Any], int, List[Dict[str, Any]]]],
    trip_nights: int,
) -> Tuple[int, List[StayPlan]]:
    """(nights in the home city, the stays elsewhere). A night on the way (a night train) is in
    neither: nobody pays for a bed."""
    n = len(layout.days)
    if country is None:
        return trip_nights, []
    counts: Dict[str, int] = {}
    home = 0
    for index in range(n - 1):
        if index in country.transit_nights:
            continue
        sleep = country.sleeps.get(index)
        if sleep is None:
            home += 1
        else:
            counts[sleep.label["ru"]] = counts.get(sleep.label["ru"], 0) + 1
    stays: List[StayPlan] = []
    for number, (overnight, _index, rows) in enumerate(stay_inputs, start=1):
        nights = counts.get(overnight["city"]["ru"], 0)
        point = (overnight["lat"], overnight["lon"])
        lodging = bud.choose_lodging(
            [bud.lodging_from_row(r) for r in rows], point, nights, needed=True
        )
        stays.append(
            StayPlan(number, overnight["city"], overnight["region"], point, nights, lodging)
        )
    return home, stays


def _annotate(
    layout: TripLayout,
    country: Optional[ctry.CountryResult],
    stays: List[StayPlan],
    home_label: Dict[str, str],
) -> None:
    """Set `overnight` of every day (None on the last one); `kind` is already on the day."""
    n = len(layout.days)
    by_city = {st.city["ru"]: st for st in stays}
    for index, day in enumerate(layout.days):
        if index == n - 1:
            day.overnight = None
            continue
        overnight = _home_json(home_label)
        if country is not None:
            target = index + 1 if index in country.transit_nights else index
            found = country.overnights.get(target)
            if found is not None:
                overnight = dict(found)
                stay = by_city.get(overnight["city"]["ru"])
                recommended = stay.lodging.recommended if stay else None
                if recommended is not None:  # the person sleeps in the recommended lodging
                    overnight["lat"], overnight["lon"] = (
                        recommended.place.lat, recommended.place.lon,
                    )  # fmt: skip
        day.overnight = overnight


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


def _options_json(plan: bud.LodgingPlan, locale: str) -> List[Dict[str, Any]]:
    return [
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


def _lodging_json(
    plan: bud.LodgingPlan, locale: str, with_options: bool, stays: Sequence[StayPlan] = ()
) -> Dict[str, Any]:
    """`cost_kzt` is the whole stay cost (every overnight point); `needed`, `nights` and `options`
    are the home city's. `stays` (Ш-61): the other overnight points, each with its own nights, cost
    and (when `with_options`) lodging options; empty for a trip in one city."""
    out: Dict[str, Any] = {
        "needed": plan.needed,
        "nights": plan.nights,
        "cost_kzt": plan.cost(),
        "price_assumed": plan.price_assumed,
        "stays": [
            dict(
                {
                    "stay": st.index,
                    "city": st.city,
                    "region": st.region,
                    "nights": st.nights,
                    "cost_kzt": st.lodging.cost(),
                    "price_assumed": st.lodging.price_assumed,
                    "no_options": st.lodging.no_options,
                },
                **({"options": _options_json(st.lodging, locale)} if with_options else {}),
            )
            for st in stays
        ],
    }
    if with_options:
        out["options"] = _options_json(plan, locale)
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
        "lodging": _lodging_json(plan.lodging, locale, with_places, plan.stays),
        "extra_transport_kzt": costs.extra_transport,  # Ш-61: in transport_kzt, no leg shows it
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
    for stay in plan.stays:  # Ш-61: no lodging in the database near an overnight point
        if stay.lodging.no_options:
            add("no_lodging_found", stay.city["en"])
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
