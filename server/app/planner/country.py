"""Ш-61: a trip across the country (SSOT §5.4 п. 1-4, 6). Deterministic; no model.

The city planner (`planner.layout`) lays one city out by day. This module sits on top of it for the
wishes that are NOT in the home city (Charyn, Kolsai, Turkistan...):

1. Far wishes are grouped by direction (single linkage, `group_radius_km`): places in the same
   direction are ONE outing, they are not visited with a return home in between.
2. A group farther than `transfer_min_km` from the home city is a TRANSFER to another city (plane,
   train or bus from `intercity.service`, the fastest affordable one); the others are OUTINGS by
   road from the home city.
3. An outing is a day trip (there and back) when the road one way is at most
   `day_trip_max_oneway_h`, else it takes nights near the place (a lodging within `stay_search_km`).
   The brief may say which (`stay_wishes`); the road time never overrides the person.
4. A wish with a date (`dated_wishes`) is hard: its block starts on that day, and a place is never
   moved to another one; if the date cannot be kept the place is reported in `unplaced`.
5. The road is part of the day: every stop is timed after the real drive (Valhalla through
   `intercity.service` for 50 km and more), a day takes only what fits between the day's start and
   end. The drive to a night's lodging and the drive home after an outing are not stops: their
   time is reserved in the day and their cost goes to `DayPlan.extra_transport_kzt`.
6. The days that are left are the home city's: `planner.layout.plan_days` plans them as before.

Every number is a row of `country_planner_settings` (seeded by data/seed/country_planner.sql);
without the rows `load_settings` returns None and the planner stays a city planner.
"""

import logging
import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from uuid import UUID

from app.db import fetch_all
from app.planner import hours as hrs
from app.planner import sql
from app.planner.layout import (
    BUFFER_MIN,
    DayPlan,
    LayoutWarning,
    Leg,
    Stop,
    Unplaced,
    _at,
)
from app.planner.model import Place
from app.planner.travel import LegProvider, leg_seconds, pick_default
from app.regions import region_for_point
from app.routing.base import Point, RoutingProvider, RoutingUnavailable
from app.routing.costs import IntercityParams, Tariff
from app.routing.fake import encode_polyline6, haversine_m
from app.routing.schemas import DirectionOption

log = logging.getLogger(__name__)

SETTING_KEYS = (
    "local_radius_km",
    "group_radius_km",
    "transfer_min_km",
    "day_trip_max_oneway_h",
    "transfer_budget_share_pct",
    "night_departure_min",
    "stay_search_km",
    "max_outing_days",
    "fallback_road_kmh",
)
RETURN_BY = 24 * 60 - 1  # a drive that ends after this does not fit the day
PUBLIC_MODES = ("plane", "train", "bus")
ROAD_MODES = ("car", "taxi", "tour")
NIGHT_MODES = ("train", "bus", "car", "taxi")  # a ride that can run through the night
ROAD_DETOUR = 1.3  # only for the estimate when no router answers (flagged `estimated`)


@dataclass(frozen=True)
class Settings:
    local_radius_km: float
    group_radius_km: float
    transfer_min_km: float
    day_trip_max_oneway_h: float
    transfer_budget_share: float  # 0..1
    night_departure_min: int
    stay_search_km: float
    max_outing_days: int
    fallback_road_kmh: float


async def load_settings(conn) -> Optional[Settings]:
    """None when the settings are not seeded (the planner then stays a city planner)."""
    rows = await fetch_all(conn, "SELECT key, value FROM country_planner_settings", ())
    values = {r["key"]: float(r["value"]) for r in rows}
    if any(key not in values for key in SETTING_KEYS):
        return None
    return Settings(
        local_radius_km=values["local_radius_km"],
        group_radius_km=values["group_radius_km"],
        transfer_min_km=values["transfer_min_km"],
        day_trip_max_oneway_h=values["day_trip_max_oneway_h"],
        transfer_budget_share=values["transfer_budget_share_pct"] / 100.0,
        night_departure_min=int(values["night_departure_min"]),
        stay_search_km=values["stay_search_km"],
        max_outing_days=int(values["max_outing_days"]),
        fallback_road_kmh=values["fallback_road_kmh"],
    )


# --- wishes ------------------------------------------------------------------------------
@dataclass(frozen=True)
class WishPlace:
    """A must-have place with what the brief says about its wish."""

    place: Place
    order: int  # position of the wish in the brief
    wish: str
    on: Optional[date] = None  # dated wish: the day it must happen
    stay: Optional[str] = None  # "day" | "overnight" | None (decide by the road)


def wish_places(brief: Mapping[str, Any], selection) -> List[WishPlace]:
    """Every must-have place of the selection with the date / stay of its wish (case-insensitive
    match on the wish text). A date that is not a valid ISO date is ignored."""
    dated: Dict[str, date] = {}
    for item in brief.get("dated_wishes") or []:
        try:
            dated[str(item["wish"]).casefold()] = date.fromisoformat(str(item["date"]))
        except (KeyError, ValueError):
            continue
    stays = {str(i["wish"]).casefold(): i["stay"] for i in brief.get("stay_wishes") or []}
    out: List[WishPlace] = []
    seen: Set[UUID] = set()
    for order, wish in enumerate(selection.must_haves):
        key = wish.text.casefold()
        for place in wish.places:
            if place.id in seen:
                continue
            seen.add(place.id)
            out.append(WishPlace(place, order, wish.text, dated.get(key), stays.get(key)))
    return out


def km(a: Point, b: Point) -> float:
    return haversine_m(a, b) / 1000.0


def pt(place: Place) -> Point:
    return (place.lat, place.lon)


def split_local_far(
    wishes: Sequence[WishPlace], home: Point, radius_km: float
) -> Tuple[List[WishPlace], List[WishPlace]]:
    """(home-city wishes, far wishes): far = farther than `radius_km` (`local_radius_km`) from the
    home point. Food wishes stay in the city (the far side has no food pool)."""
    local, far = [], []
    for w in wishes:
        if not w.place.is_food and km(home, pt(w.place)) > radius_km:
            far.append(w)
        else:
            local.append(w)
    return local, far


def cluster_by_direction(far: Sequence[WishPlace], radius_km: float) -> List[List[WishPlace]]:
    """Single linkage: places closer than `radius_km` to each other (directly or through others)
    form one group. Groups and their members keep the order of the wishes."""
    parent = list(range(len(far)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(far)):
        for j in range(i + 1, len(far)):
            if km(pt(far[i].place), pt(far[j].place)) <= radius_km:
                parent[find(j)] = find(i)
    groups: Dict[int, List[WishPlace]] = {}
    for i, item in enumerate(far):
        groups.setdefault(find(i), []).append(item)
    return sorted(groups.values(), key=lambda g: min(w.order for w in g))


def split_by_dates(groups: Sequence[List[WishPlace]]) -> List[List[WishPlace]]:
    """A group whose wishes have different dates cannot be one outing (each date is hard): it
    is split, one group per date, the wishes without a date go with the first one."""
    out: List[List[WishPlace]] = []
    for group in groups:
        dates = sorted({x.on for x in group if x.on is not None})
        if len(dates) < 2:
            out.append(list(group))
            continue
        parts: Dict[date, List[WishPlace]] = {d: [] for d in dates}
        for x in group:
            parts[x.on or dates[0]].append(x)
        out.extend(parts[d] for d in dates)
    return out


# --- hops: one move between two points ---------------------------------------------------
@dataclass
class Hop:
    leg: Leg
    cost_max: int  # upper cost of the default option
    options: List[Dict[str, Any]] = field(default_factory=list)  # raw intercity options, if any

    @property
    def minutes(self) -> int:
        return int(math.ceil(self.leg.travel_s / 60.0))


@dataclass
class World:
    """What the planning of the far part reads, held for one `plan_country` call."""

    conn: Any
    router: RoutingProvider
    tariffs: Dict[str, Tariff]
    params: IntercityParams
    legs: LegProvider
    settings: Settings
    hours: Mapping[UUID, hrs.HoursRows]
    dates: List[date]
    start_min: int
    end_min: int
    cap: int
    budget_kzt: int
    home: Point
    home_label: Dict[str, str]
    home_region: str
    estimated: bool = False
    unknown_prices: int = 0
    labels: Dict[Point, Dict[str, str]] = field(default_factory=dict)
    regions: Dict[Point, str] = field(default_factory=dict)
    raw_cache: Dict[Tuple[Point, Point, date], List[Dict[str, Any]]] = field(default_factory=dict)
    lodging_cache: Dict[Point, Optional[Dict[str, Any]]] = field(default_factory=dict)
    hop_cache: Dict[Any, Hop] = field(default_factory=dict)


CITY_LABEL = """
SELECT city_ru, city_en FROM intercity_hubs
WHERE ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                 catchment_km * 1000)
ORDER BY ST_Distance(location::geography,
                     ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography), id
LIMIT 1
"""


async def city_label(w: World, point: Point, fallback: Optional[Place] = None) -> Dict[str, str]:
    """{ru, en} name of the town around a point: the nearest intercity hub that serves it, else the
    place's own name (an outing's sight), else the home city."""
    if km(point, w.home) <= w.settings.local_radius_km:
        return dict(w.home_label)
    key = (round(point[0], 3), round(point[1], 3))
    if key not in w.labels:
        row = await fetch_all(w.conn, CITY_LABEL, {"lat": point[0], "lon": point[1]})
        if row:
            w.labels[key] = {"ru": row[0]["city_ru"], "en": row[0]["city_en"]}
        elif fallback is not None:
            w.labels[key] = {
                "ru": fallback.name_ru or fallback.name_en or "",
                "en": fallback.name_en or fallback.name_ru or "",
            }
        else:
            w.labels[key] = dict(w.home_label)
    return w.labels[key]


async def region_id(w: World, point: Point) -> str:
    key = (round(point[0], 3), round(point[1], 3))
    if key not in w.regions:
        region = await region_for_point(w.conn, point[0], point[1])
        w.regions[key] = region.id if region else w.home_region
    return w.regions[key]


async def overnight_json(w: World, point: Point, label: Dict[str, str]) -> Dict[str, Any]:
    return {
        "city": dict(label),
        "region": await region_id(w, point),
        "lat": point[0],
        "lon": point[1],
    }


async def raw_options(
    w: World, a: Point, b: Point, on: date, now: datetime
) -> List[Dict[str, Any]]:
    """Intercity options (`intercity.service`) between two points; [] = none (or no router)."""
    from app.intercity.service import intercity_options  # late: it imports the routing service

    key = (a, b, on)
    if key not in w.raw_cache:
        try:
            w.raw_cache[key] = await intercity_options(
                w.conn, w.router, w.tariffs, w.params, a, b, on, "ru", now
            )
        except RoutingUnavailable:
            w.raw_cache[key] = []
    return w.raw_cache[key]


def rank_options(
    raw: Sequence[Dict[str, Any]], transfer: bool, cap_kzt: float
) -> List[Dict[str, Any]]:
    """The options in the order the planner prefers them (the first is the default).

    Transfer between cities: plane / train / bus, the fastest one that is affordable (upper price at
    most `cap_kzt`, unknown price counts as affordable), then the unaffordable ones by price; a
    mode that does not run on the date is left out. A road (outing): the option the intercity
    service recommends if affordable, then the others by time."""
    usable = [o for o in raw if (o.get("schedule") or {}).get("runs_on_date") is not False]
    wanted = PUBLIC_MODES if transfer else ROAD_MODES
    pool = [o for o in usable if o["mode"] in wanted] or usable

    def affordable(o: Dict[str, Any]) -> bool:
        return o["cost_kzt_max"] is None or o["cost_kzt_max"] <= cap_kzt

    good = [o for o in pool if affordable(o)]
    bad = [o for o in pool if not affordable(o)]
    if transfer:
        good.sort(key=lambda o: (o["duration_s_max"], o["mode"]))
    else:
        good.sort(key=lambda o: (not o.get("recommended"), o["duration_s_max"], o["mode"]))
    bad.sort(key=lambda o: (o["cost_kzt_max"], o["duration_s_max"], o["mode"]))
    rest = [o for o in usable if o not in pool]
    return good + bad + rest


def _direction_option(
    o: Dict[str, Any], a: Point, b: Point, chosen: bool, depart: datetime
) -> DirectionOption:
    arrive = depart + timedelta(seconds=o["duration_s_max"])
    return DirectionOption(
        mode=o["mode"],
        duration_s=o["duration_s"],
        duration_s_min=o["duration_s_min"],
        duration_s_max=o["duration_s_max"],
        distance_m=float(o.get("distance_m") or haversine_m(a, b)),
        cost_kzt_min=int(o["cost_kzt_min"] or 0),
        cost_kzt_max=int(o["cost_kzt_max"] or 0),
        geometry=o.get("geometry") or encode_polyline6([a, b]),
        approximate=bool(o["approximate"]),
        recommended=chosen,
        arrive_at=arrive.isoformat(),
    )


def _estimate_option(w: World, a: Point, b: Point) -> Dict[str, Any]:
    """A straight-line drive when no router answers: the leg exists and is flagged estimated."""
    metres = haversine_m(a, b) * ROAD_DETOUR
    seconds = metres / 1000.0 / w.settings.fallback_road_kmh * 3600.0
    fuel = float(w.params.fuel_per_km_kzt) * metres / 1000.0
    return {
        "mode": "car", "duration_s": round(seconds), "duration_s_min": round(seconds),
        "duration_s_max": round(seconds), "cost_kzt_min": round(fuel), "cost_kzt_max": round(fuel),
        "approximate": True, "distance_m": round(metres), "geometry": None, "schedule": None,
        "recommended": True,
    }  # fmt: skip


async def hop(
    w: World,
    a: Point,
    b: Point,
    depart: datetime,
    origin_pid: Optional[UUID],
    dest: Place,
    transfer: bool = False,
    only_option: Optional[Dict[str, Any]] = None,
    origin_place: Optional[Place] = None,
) -> Hop:
    """One leg from `a` to the place `dest`. Under `min_distance_km` an ordinary city leg (Ш-22
    options); from there an intercity leg: all options of `intercity.service`, the preferred one is
    the default. `only_option`: the option a transfer day already chose."""
    key = (a, b, depart.strftime("%Y-%m-%d %H"), only_option["mode"] if only_option else None)
    cached = w.hop_cache.get(key)
    if cached is not None:
        leg = cached.leg
        return Hop(
            Leg(origin_pid, dest.id, depart, leg.options, leg.default_mode, leg.travel_s,
                leg.estimated, leg.intercity),
            cached.cost_max, cached.options,
        )  # fmt: skip
    if km(a, b) < w.params.min_distance_km:
        options = await w.legs.options(a, b, depart)
        default = pick_default(options)
        if default is not None:
            travel_s, estimated = leg_seconds(default), False
            cost = int(default.cost_kzt_max)
        else:
            seconds = haversine_m(a, b) * ROAD_DETOUR / 1000.0 / 25.0 * 3600.0
            travel_s, estimated, cost = seconds, True, 0
        w.estimated = w.estimated or estimated
        result = Hop(
            Leg(origin_pid, dest.id, depart, options, default.mode if default else None,
                travel_s, estimated, None),
            cost,
        )  # fmt: skip
    else:
        raw = await raw_options(w, a, b, depart.date(), depart)
        estimated = not raw
        if estimated:
            raw = [_estimate_option(w, a, b)]
            w.estimated = True
        cap = w.budget_kzt * w.settings.transfer_budget_share
        ranked = rank_options(raw, transfer, cap)
        if only_option is not None:  # the mode a transfer day chose (same mode, this date's data)
            ranked = [o for o in raw if o["mode"] == only_option["mode"]] or ranked
        chosen = ranked[0]
        if chosen["cost_kzt_max"] is None:
            w.unknown_prices += 1
        options = [_direction_option(o, a, b, o is chosen, depart) for o in raw]
        block = {
            "mode": chosen["mode"],
            "from_city": await city_label(w, a, origin_place),
            "to_city": await city_label(w, b, dest),
            "approximate": bool(chosen["approximate"]),
            "price_kzt_min": chosen["cost_kzt_min"],
            "price_kzt_max": chosen["cost_kzt_max"],
        }
        picked = next(o for o in options if o.recommended)
        result = Hop(
            Leg(origin_pid, dest.id, depart, options, chosen["mode"], leg_seconds(picked),
                estimated, block),
            int(chosen["cost_kzt_max"] or 0), raw,
        )  # fmt: skip
    w.hop_cache[key] = result
    return result


async def road_minutes(w: World, a: Point, b: Point, on: date, dest: Place) -> int:
    """One-way minutes by the default road option (for the day trip / overnight decision)."""
    return (await hop(w, a, b, _at(on, w.start_min), None, dest)).minutes


# --- lodging near a point ----------------------------------------------------------------
async def nearest_lodging(w: World, near: Point) -> Optional[Dict[str, Any]]:
    """The lodging row nearest to `near` within `stay_search_km` (the most popular on a tie)."""
    key = (round(near[0], 3), round(near[1], 3))
    if key not in w.lodging_cache:
        rows = await fetch_all(
            w.conn,
            sql.LODGING_NEAR,
            {"lat": near[0], "lon": near[1], "radius_m": w.settings.stay_search_km * 1000},
        )
        rows.sort(
            key=lambda r: (km(near, (r["lat"], r["lon"])), -(r["popularity"] or 0), str(r["id"]))
        )
        w.lodging_cache[key] = rows[0] if rows else None
    return w.lodging_cache[key]


@dataclass
class Sleep:
    point: Point
    label: Dict[str, str]
    found: bool  # a lodging exists there (else the point of the place stands for it)


async def sleep_near(w: World, near: Point, place: Place) -> Sleep:
    row = await nearest_lodging(w, near)
    if row is not None:
        point = (row["lat"], row["lon"])
        return Sleep(point, await city_label(w, point, place), True)
    return Sleep(near, await city_label(w, near, place), False)


# --- blocks ------------------------------------------------------------------------------
@dataclass
class BlockDay:
    stops: List[Stop] = field(default_factory=list)
    legs: List[Leg] = field(default_factory=list)
    kind: str = "regular"
    sleep: Optional[Sleep] = None  # None: sleeps at home
    extra_kzt: int = 0
    night_ride_before: bool = False  # the night before was spent on the way here


@dataclass
class Block:
    kind: str  # "outing" | "transfer"
    wishes: List[WishPlace]
    pin: Optional[int] = None  # index of the day its dated wish asks for
    days: List[BlockDay] = field(default_factory=list)
    start: int = 0  # first day index once simulated
    unplaced: List[Unplaced] = field(default_factory=list)


def _visit_start(
    w: World, place: Place, on: date, arrive_min: int
) -> Tuple[Optional[int], int, bool]:
    """(start minute or None when it does not fit the day, visit minutes, hours assumed)."""
    wins = hrs.windows(w.hours.get(place.id), on)
    assumed = wins is None
    if wins is None:
        wins = [hrs.ASSUMED_WINDOW]
    visit = hrs.visit_minutes(place)
    start = hrs.earliest_start(wins, max(arrive_min, w.start_min), visit)
    if start is None or start + visit > w.end_min:
        return None, visit, assumed
    return start, visit, assumed


def _stop(wish: WishPlace, on: date, start: int, visit: int, assumed: bool) -> Stop:
    return Stop(
        place=wish.place, kind="activity", meal=None, start=_at(on, start),
        end=_at(on, start + visit), visit_min=visit, must_have=True, hours_assumed=assumed,
    )  # fmt: skip


def order_within(
    wishes: Sequence[WishPlace], home: Point, minutes: Optional[Mapping[UUID, int]] = None
) -> List[WishPlace]:
    """Visit order of one group: a dated wish first (it fixes the day), then by the road time from
    the home city (`minutes`, else the straight distance): out along one road and back, nothing
    visited twice. A mountain place can be nearer on the map than by road, so the road decides."""

    def far(x: WishPlace) -> float:
        return minutes[x.place.id] if minutes and x.place.id in minutes else km(home, pt(x.place))

    return sorted(wishes, key=lambda x: (x.on is None, x.on or date.min, far(x), x.order))


async def decide_overnight(w: World, wishes: Sequence[WishPlace], on: date) -> bool:
    """Day trip or nights near the place. The person's word first (`stay_wishes`), else the road:
    one way longer than `day_trip_max_oneway_h` (the farthest place of the group) = overnight."""
    stays = {x.stay for x in wishes if x.stay}
    if "overnight" in stays:
        return True
    if "day" in stays:
        return False
    longest = 0
    for x in wishes:
        longest = max(longest, await road_minutes(w, w.home, pt(x.place), on, x.place))
    return longest > w.settings.day_trip_max_oneway_h * 60


async def simulate_outing(
    w: World, wishes: Sequence[WishPlace], first: int, overnight: bool
) -> Tuple[List[BlockDay], List[Unplaced]]:
    """The days of one outing from the home city, starting on day index `first`.

    A stop is timed after the real drive; when the next place does not fit the day, an overnight
    outing sleeps near it (the evening drive is reserved, its cost goes to `extra_kzt`) and goes on
    the next day, a day trip gives the rest up (reported). After the last place the way home is
    driven the same day if it fits and the outing had a night, else the person sleeps there and a
    drive-home day (no stops) follows."""
    days: List[BlockDay] = []
    unplaced: List[Unplaced] = []
    rest = list(wishes)
    idx, day_no = first, 0
    cur: Optional[BlockDay] = BlockDay()
    t = w.start_min
    loc, loc_pid, loc_place = w.home, None, None  # where the day started / the last stop is

    def give_up(items: Sequence[WishPlace], on: Optional[date]) -> None:
        for x in items:
            unplaced.append(Unplaced(x.place, "no_time", True, on))

    while rest:
        assert cur is not None
        if idx >= len(w.dates) or len(days) >= w.settings.max_outing_days:
            give_up(rest, None)
            break
        on = w.dates[idx]
        x = rest[0]
        place = x.place
        move = await hop(w, loc, pt(place), _at(on, t), loc_pid if cur.stops else None, place,
                         origin_place=loc_place)  # fmt: skip
        arrive = t + move.minutes + (BUFFER_MIN if cur.stops else 0)
        start, visit, assumed = _visit_start(w, place, on, arrive)
        last = len(rest) == 1
        back: Optional[Hop] = None
        if start is not None and last:
            back = await hop(w, pt(place), w.home, _at(on, start + visit), None, place,
                             origin_place=place)  # fmt: skip
        fits = start is not None and (
            not last
            or overnight
            or (back is not None and start + visit + back.minutes <= RETURN_BY)
        )
        if fits:
            assert start is not None
            cur.stops.append(_stop(x, on, start, visit, assumed))
            cur.legs.append(move.leg)
            t, loc, loc_pid, loc_place = start + visit, pt(place), place.id, place
            rest.pop(0)
            if last:
                assert back is not None
                if (day_no > 0 or not overnight) and t + back.minutes <= RETURN_BY:
                    # home the same evening
                    cur.extra_kzt += back.cost_max
                    days.append(cur)
                else:  # the night is here; the drive home is the next morning
                    cur.sleep = await sleep_near(w, pt(place), place)
                    days.append(cur)
                    if idx + 1 < len(w.dates):
                        days.append(BlockDay(kind="transfer", extra_kzt=back.cost_max))
                cur = None
            continue
        # the place does not fit today
        if cur.stops:
            if not overnight:
                give_up(rest, on)
                break
            sleep = await sleep_near(w, pt(place), place)
            evening = await hop(
                w, loc, sleep.point, _at(on, t), None, place, origin_place=loc_place
            )
            if t + evening.minutes > RETURN_BY:  # too late to get there: stay where we are
                sleep = await sleep_near(w, loc, place)
                evening = await hop(w, loc, sleep.point, _at(on, t), None, place,
                                    origin_place=loc_place)  # fmt: skip
            cur.sleep, cur.extra_kzt = sleep, cur.extra_kzt + evening.cost_max
        elif overnight and day_no == 0:
            # a drive day: the road to the place alone takes the day; sleep near it
            sleep = await sleep_near(w, pt(place), place)
            drive = await hop(w, loc, sleep.point, _at(on, t), None, place, origin_place=None)
            cur.kind, cur.sleep, cur.extra_kzt = "transfer", sleep, drive.cost_max
        else:
            give_up([x], on)  # closed that day, or it never fits
            rest.pop(0)
            continue
        days.append(cur)
        idx += 1
        day_no += 1
        assert cur.sleep is not None
        cur = BlockDay()
        t, loc, loc_pid, loc_place = w.start_min, days[-1].sleep.point, None, None  # type: ignore[union-attr]
    if cur is not None and cur.stops:  # a day trip: home the same day
        back = await hop(w, loc, w.home, _at(w.dates[min(idx, len(w.dates) - 1)], t), None,
                         loc_place or wishes[0].place, origin_place=loc_place)  # fmt: skip
        cur.extra_kzt += back.cost_max
        days.append(cur)
    return days, unplaced


async def simulate_transfer(
    w: World, wishes: Sequence[WishPlace], first: int, origin: Point, origin_place: Optional[Place]
) -> Tuple[List[BlockDay], List[Unplaced]]:
    """A move to another city on day `first` and the days there. The ride is the fastest affordable
    plane / train / bus that fits: the same day (it leaves at the day's start), or at night from the
    day before (a train or bus; the night is spent on the way). The places of the city follow, a
    day takes `cap` of them at most."""
    first_place = wishes[0].place
    on = w.dates[first]

    def fail(reason: str) -> Tuple[List[BlockDay], List[Unplaced]]:
        return [], [Unplaced(x.place, reason, True, on) for x in wishes]

    raw = await raw_options(w, origin, pt(first_place), on, _at(on, w.start_min))
    if not raw:
        return fail("no_transport")
    cap = w.budget_kzt * w.settings.transfer_budget_share
    visit0 = hrs.visit_minutes(first_place)
    chosen, night = None, False
    for option in rank_options(raw, True, cap):
        minutes = int(math.ceil(option["duration_s_max"] / 60.0))
        if w.start_min + minutes + BUFFER_MIN + visit0 <= w.end_min:
            chosen, night = option, False
            break
        arrive = max(w.settings.night_departure_min + minutes - 24 * 60, w.start_min)
        if (
            first >= 1
            and option["mode"] in NIGHT_MODES
            and arrive + BUFFER_MIN + visit0 <= w.end_min
        ):
            chosen, night = option, True
            break
    if chosen is None:
        return fail("no_time")
    minutes = int(math.ceil(chosen["duration_s_max"] / 60.0))
    if night:
        depart = _at(w.dates[first - 1], w.settings.night_departure_min)
        arrive_min = max(w.settings.night_departure_min + minutes - 24 * 60, w.start_min)
    else:
        depart = _at(on, w.start_min)
        arrive_min = w.start_min + minutes
    days: List[BlockDay] = []
    unplaced: List[Unplaced] = []
    cur = BlockDay(kind="transfer", night_ride_before=night)
    loc, loc_pid, loc_place = origin, None, origin_place
    t = arrive_min
    idx = first
    rest = list(wishes)
    while rest:
        if idx >= len(w.dates):
            unplaced += [Unplaced(x.place, "no_time", True, None) for x in rest]
            break
        day = w.dates[idx]
        x = rest[0]
        if idx == first and not cur.stops:  # the ride itself is the leg into the first stop
            move = await hop(w, origin, pt(x.place), depart, None, x.place, transfer=True,
                             only_option=chosen, origin_place=origin_place)  # fmt: skip
            arrive = arrive_min + BUFFER_MIN
        elif not cur.stops:  # first stop of a later day: the day starts in town
            move = None
            arrive = w.start_min
        else:
            move = await hop(w, loc, pt(x.place), _at(day, t), loc_pid, x.place,
                             origin_place=loc_place)  # fmt: skip
            arrive = t + move.minutes + BUFFER_MIN
        start, visit, assumed = _visit_start(w, x.place, day, arrive)
        if start is not None and len(cur.stops) < w.cap:
            if move is not None:
                cur.legs.append(move.leg)
            cur.stops.append(_stop(x, day, start, visit, assumed))
            t, loc, loc_pid, loc_place = start + visit, pt(x.place), x.place.id, x.place
            rest.pop(0)
            continue
        if not cur.stops and idx > first:  # closed that day even from a fresh start
            unplaced.append(Unplaced(x.place, "no_time", True, day))
            rest.pop(0)
            continue
        if not cur.stops:  # nothing fits the arrival day (checked above for the first place)
            unplaced.append(Unplaced(x.place, "no_time", True, day))
            rest.pop(0)
            continue
        days.append(cur)  # the day is full: the next day in the city
        idx += 1
        cur = BlockDay()
        t, loc_pid = w.start_min, None
    if cur.stops:
        days.append(cur)
    if days:
        sleep = await sleep_near(w, pt(first_place), first_place)
        for bd in days:
            bd.sleep = sleep
    return days, unplaced


# --- allocation ---------------------------------------------------------------------------
@dataclass
class CountryResult:
    days: Dict[int, DayPlan]  # the days the far part occupies, by day index
    home_indices: List[int]
    overnights: Dict[
        int, Optional[Dict[str, Any]]
    ]  # day index -> overnight (None = sleeps at home)
    transit_nights: Set[int]  # day indexes whose night is spent on the way
    sleeps: Dict[int, Sleep]
    unplaced: List[Unplaced]
    warnings: List[LayoutWarning]
    estimated: bool
    blocks: List[Block] = field(default_factory=list)


def _free_window(occupied: List[bool], length: int) -> Optional[int]:
    for i in range(len(occupied) - length + 1):
        if not any(occupied[i : i + length]):
            return i
    return None


def _last_free_window(occupied: List[bool], length: int) -> Optional[int]:
    for i in range(len(occupied) - length, -1, -1):
        if not any(occupied[i : i + length]):
            return i
    return None


def _origin_of(w: World, placed: Sequence[Block]) -> Tuple[Point, Optional[Place]]:
    """Where a transfer starts: the last transfer city already planned, else the home city."""
    done = [b for b in placed if b.kind == "transfer" and b.days]
    if not done:
        return w.home, None
    last = max(done, key=lambda b: b.start)
    stop = [s for d in last.days for s in d.stops][-1]
    return (stop.place.lat, stop.place.lon), stop.place


def _day_plan(bd: BlockDay, on: date) -> DayPlan:
    return DayPlan(
        on, list(bd.stops), list(bd.legs), kind=bd.kind, extra_transport_kzt=bd.extra_kzt
    )  # fmt: skip


async def plan_country(w: World, far: Sequence[WishPlace]) -> CountryResult:
    """Lay the far wishes out over the days (rules in the module doc); the days that stay free are
    the home city's (`CountryResult.home_indices`)."""
    n = len(w.dates)
    result = CountryResult({}, [], {}, set(), {}, [], [], False)
    occupied = [False] * n
    blocks: List[Block] = []
    wishes: List[WishPlace] = []
    for x in far:
        if x.on is not None and x.on not in w.dates:  # not a day of the trip: the wish stays
            result.warnings.append(LayoutWarning("dated_wish_out_of_range", x.on, x.place.name))
            x = replace(x, on=None)
        wishes.append(x)
    for group in split_by_dates(cluster_by_direction(wishes, w.settings.group_radius_km)):
        centre = (
            sum(x.place.lat for x in group) / len(group),
            sum(x.place.lon for x in group) / len(group),
        )
        kind = "transfer" if km(w.home, centre) > w.settings.transfer_min_km else "outing"
        road = {
            x.place.id: await road_minutes(w, w.home, pt(x.place), w.dates[0], x.place)
            for x in group
        }
        ordered = order_within(group, w.home, road)
        pins = [w.dates.index(x.on) for x in ordered if x.on is not None]
        blocks.append(Block(kind, ordered, pin=min(pins) if pins else None))
    placed: List[Block] = []

    async def settle(block: Block, start: int) -> None:
        """Simulate the block from `start`. A dated wish that lands on another day moves the BLOCK
        (earlier by the difference), never the wish; a dated place that still misses its day is
        reported, not moved."""
        days: List[BlockDay] = []
        unplaced: List[Unplaced] = []
        for attempt in range(2):
            if block.kind == "outing":
                overnight = await decide_overnight(w, block.wishes, w.dates[start])
                days, unplaced = await simulate_outing(w, block.wishes, start, overnight)
            else:
                origin, origin_place = _origin_of(w, placed)
                days, unplaced = await simulate_transfer(
                    w, block.wishes, start, origin, origin_place
                )
            wanted_start = None
            for k, bd in enumerate(days):
                for stop in bd.stops:
                    wish = next(x for x in block.wishes if x.place.id == stop.place.id)
                    if wish.on in w.dates and w.dates.index(wish.on) != start + k:
                        wanted_start = w.dates.index(wish.on) - k
                        break
                if wanted_start is not None:
                    break
            if (
                attempt == 0
                and wanted_start is not None
                and 0 <= wanted_start != start
                and not any(occupied[wanted_start : wanted_start + len(days)])
            ):
                start = wanted_start
                continue
            break
        for k, bd in enumerate(days):  # a dated place off its day is reported, never kept
            for stop in list(bd.stops):
                wish = next(x for x in block.wishes if x.place.id == stop.place.id)
                if wish.on is not None and wish.on != w.dates[min(start + k, n - 1)]:
                    i = bd.stops.index(stop)
                    bd.stops.pop(i)
                    if i < len(bd.legs):
                        bd.legs.pop(i)
                    unplaced.append(Unplaced(wish.place, "no_time", True, wish.on))
        block.days = [bd for bd in days if bd.stops or bd.kind == "transfer" or bd.sleep]
        block.unplaced, block.start = unplaced, start

    def fits(block: Block) -> bool:
        end = block.start + len(block.days)
        return bool(block.days) and end <= n and not any(occupied[block.start : end])

    async def place(block: Block, find_start) -> bool:
        length = 1
        for _ in range(4):
            start = find_start(length)
            if start is None:
                return False
            await settle(block, start)
            if len(block.days) > length and block.pin is None:
                length = len(block.days)
                continue
            if fits(block):
                for k in range(len(block.days)):
                    occupied[block.start + k] = True
                placed.append(block)
                return True
            return False
        return False

    def fail(block: Block) -> None:
        result.unplaced += block.unplaced or [
            Unplaced(x.place, "no_time", True, x.on) for x in block.wishes
        ]
        block.days = []

    # 1. dated blocks first, in date order (the later of two that collide is reported)
    for block in sorted([b for b in blocks if b.pin is not None], key=lambda b: b.pin or 0):
        after_a_move = block.kind == "outing" and any(
            b.kind == "transfer" and b.start < (block.pin or 0) for b in placed
        )  # the person is in another city by then: no outing from home
        if after_a_move or not await place(block, lambda length, b=block: b.pin):
            fail(block)
    # 2. transfers without a date: the last days of the trip, the farthest city last
    free_transfers = sorted(
        [b for b in blocks if b.kind == "transfer" and b.pin is None],
        key=lambda b: km(w.home, (b.wishes[0].place.lat, b.wishes[0].place.lon)),
    )
    for block in reversed(free_transfers):
        if not await place(block, lambda length: _last_free_window(occupied, length)):
            fail(block)
    # after a move to another city the trip stays there (no way back is planned): the days from the
    # first transfer on are not available to outings from the home city
    moved = [b.start for b in placed if b.kind == "transfer"]
    for index in range(min(moved) if moved else n, n):
        occupied[index] = True
    # 3. outings without a date: the earliest free window that is long enough
    for block in [b for b in blocks if b.kind == "outing" and b.pin is None]:
        if not await place(block, lambda length: _free_window(occupied, length)):
            fail(block)
    for block in placed:
        result.unplaced += block.unplaced
        for k, bd in enumerate(block.days):
            index = block.start + k
            result.days[index] = _day_plan(bd, w.dates[index])
            if bd.sleep is not None:
                result.sleeps[index] = bd.sleep
                result.overnights[index] = await overnight_json(w, bd.sleep.point, bd.sleep.label)
            else:
                result.overnights[index] = None
            if bd.night_ride_before and index >= 1:
                result.transit_nights.add(index - 1)
    # the days after the last transfer are spent in that city: nothing planned there, but the
    # person sleeps there (and pays for it)
    stayed = [b for b in placed if b.kind == "transfer" and b.days]
    if stayed:
        last = max(stayed, key=lambda b: b.start)
        sleep = last.days[-1].sleep
        for index in range(last.start + len(last.days), n):
            if index in result.days:
                continue
            result.days[index] = _day_plan(BlockDay(sleep=sleep), w.dates[index])
            if sleep is not None:
                result.sleeps[index] = sleep
                result.overnights[index] = await overnight_json(w, sleep.point, sleep.label)
    result.blocks = placed
    result.home_indices = [i for i in range(n) if i not in result.days]
    result.estimated = w.estimated
    if w.unknown_prices:
        result.warnings.append(LayoutWarning("transfer_price_unknown", None, str(w.unknown_prices)))
    return result
