"""Ш-34: lay the selected places out by day and time. Deterministic; no model, no randomness.

`plan_days(...)` takes the places of Ш-33 and returns a `TripLayout`, an in-memory plan that
Ш-36 persists into trips / trip_items / trip_legs. Steps:

1. Day capacity by pace (constants below). Activities per day come from `scoring
   .ACTIVITIES_PER_DAY`, the same numbers that size the Ш-33 pools; a mountain place weighs 2.
2. Mountains: each goes to its own day where possible, the day with the least rain in the
   morning (unknown forecast: the first day it is open), and is the first stop of that day.
3. Clustering: capacity-constrained k-means (k = days, haversine) around seeds picked
   farthest-first; must-haves are placed first and may exceed the capacity, others only fit.
   Outdoor places avoid days that are mostly rainy when an alternative exists.
4. Meals: lunch and dinner every day. Cuisine must-haves take a slot first; the rest come from
   the food pool, close to the day's centre, open in the meal window.
5. Order inside a day: nearest neighbour, meals inserted at their best position, then 2-opt and
   relocate moves on (violations, rainy outdoor stops, finish time) over the travel matrix.
6. Timing with real legs (Ш-22 options): stops are timed one after another; a stop that no
   longer fits is dropped, and a dropped must-have is reported in `unplaced`, never silently.

Start of the day: `start_point` (the lodging, Ш-35 will provide it) or, by default, the city
centre; then the first stop has no leg from the start. The brief has only `has_accommodation`.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from uuid import UUID

from app.planner import hours as hrs
from app.planner import scoring
from app.planner.model import Place
from app.planner.travel import (
    LegProvider,
    TravelMatrixProvider,
    TravelTimes,
    leg_seconds,
    pick_default,
)
from app.planner.weather import Forecast, UnknownForecast, is_rainy
from app.regions import default_region
from app.routing.base import Point
from app.routing.fake import haversine_m
from app.routing.schemas import DirectionOption

log = logging.getLogger(__name__)

# --- capacity ---------------------------------------------------------------------------
# Active hours of a day by pace (minutes since midnight): everything, meals included, happens
# between DAY_START and DAY_END. Active hours = END - START: calm 10 h, normal 11.5 h, dense 13 h.
DAY_START = {"calm": 10 * 60, "normal": 9 * 60 + 30, "dense": 9 * 60}
DAY_END = {"calm": 20 * 60, "normal": 21 * 60, "dense": 22 * 60}
# Activities (non-food stops) per day = scoring.ACTIVITIES_PER_DAY: calm 3, normal 4, dense 6.
MOUNTAIN_WEIGHT = 2  # a mountain place takes the room of two activities
BUFFER_MIN = 5  # between the end of a visit and the departure
KMEANS_ITERATIONS = 4
RAIN_DAY_SKIP = 0.5  # share of rainy active hours from which a day is "rainy" for outdoor places


@dataclass(frozen=True)
class MealRule:
    earliest: int  # start not before (minutes)
    latest_start: int
    visit_min: int


MEALS: Dict[str, MealRule] = {
    "lunch": MealRule(12 * 60, 14 * 60 + 30, 60),
    "dinner": MealRule(18 * 60, 20 * 60 + 30, 75),
}
# Food that is not a meal: it can be a must-have stop, never a lunch or dinner.
NON_MEAL_CATEGORIES = {"coffee", "bakery", "bar", "nightclub"}


# --- plan structures (Ш-36 persists these) -------------------------------------------------------
@dataclass
class Stop:  # -> trip_items
    place: Place
    kind: str  # "activity" | "meal"
    meal: Optional[str]  # "lunch" | "dinner" | None
    start: datetime  # region time zone
    end: datetime
    visit_min: int
    must_have: bool
    hours_assumed: bool = False  # no opening hours in the database; 09:00-21:00 assumed
    rain_exposed: bool = False  # outdoor and the forecast says rain, no better slot existed


@dataclass
class Leg:  # -> trip_legs
    origin_place_id: Optional[UUID]  # None = the day's start point (lodging)
    destination_place_id: UUID
    depart_at: datetime
    options: List[DirectionOption]
    default_mode: Optional[str]  # the Ш-22 recommended option; None when no option was computed
    travel_s: float  # time the schedule reserves for this leg
    estimated: bool  # no router options: the time is a straight-line estimate
    # Ш-61: a move between cities or a long road (`planner.country`): {mode, from_city, to_city,
    # approximate, price_kzt_min, price_kzt_max}; None for an ordinary leg
    intercity: Optional[Dict[str, Any]] = None


@dataclass
class DayPlan:
    date: date
    stops: List[Stop] = field(default_factory=list)
    legs: List[Leg] = field(default_factory=list)  # legs[i] ends at stops[i] (+ start leg first)
    # Ш-61 (set by `planner.build`): "regular" | "transfer" (the day is mostly an intercity move);
    # where the person sleeps that night ({city: {ru, en}, region, lat, lon}), None on the last day
    kind: str = "regular"
    overnight: Optional[Dict[str, Any]] = None
    # road the schedule reserves but no leg shows (the evening drive to a night's lodging, the drive
    # home after an outing): its upper cost, counted in the budget's transport
    extra_transport_kzt: int = 0


@dataclass
class Unplaced:
    place: Place
    reason: str  # "closed_on_trip_days" | "no_time"
    must_have: bool
    date: Optional[date] = None


@dataclass
class LayoutWarning:
    code: str  # "travel_estimated" | "meal_missing" | "hours_assumed"
    date: Optional[date] = None
    detail: Optional[str] = None


@dataclass
class TripLayout:
    days: List[DayPlan]
    unplaced: List[Unplaced] = field(default_factory=list)
    warnings: List[LayoutWarning] = field(default_factory=list)
    start_point: Point = field(default_factory=lambda: default_region().centre)
    start_point_default: bool = True
    travel_estimated: bool = False

    @property
    def must_have_unplaced(self) -> List[Unplaced]:
        return [u for u in self.unplaced if u.must_have]


# --- working items ----------------------------------------------------------------------
@dataclass
class _Item:
    place: Place
    kind: str
    meal: Optional[str]
    must: bool
    visit: int
    wins: List[hrs.Window]
    assumed: bool
    earliest: int  # not before (meal window start, else 0)
    latest_start: int  # (meal window end, else 1440)
    rank: int  # lower = more wanted; must-haves are -1
    weight: int = 1

    @property
    def outdoor(self) -> bool:
        return self.place.outdoor or self.place.setting == "outdoor"


def _pt(place: Place) -> Point:
    return (place.lat, place.lon)


def _dist_km(a: Point, b: Point) -> float:
    return haversine_m(a, b) / 1000.0


def _centroid(points: Sequence[Point], default: Point) -> Point:
    if not points:
        return default
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


@dataclass
class _Ctx:
    dates: List[date]
    start_min: int
    end_min: int
    cap: int
    hours: Mapping[UUID, hrs.HoursRows]
    forecast: Forecast
    start_point: Point

    def rain_hours(self, day: date) -> Set[int]:
        return {h for h in range(24) if is_rainy(self.forecast, day, h)}

    def rain_share(self, day: date) -> float:
        span = range(self.start_min // 60, (self.end_min + 59) // 60)
        rainy = self.rain_hours(day)
        return sum(1 for h in span if h in rainy) / max(1, len(span))

    def morning_rain(self, day: date) -> float:
        total = 0.0
        for h in range(self.start_min // 60, self.start_min // 60 + 5):
            p = self.forecast.rain_probability(day, h)
            total += p or 0.0
        return total

    def make_item(
        self,
        place: Place,
        day: date,
        kind: str,
        must: bool,
        rank: int,
        meal: Optional[str] = None,
    ) -> _Item:
        wins = hrs.windows(self.hours.get(place.id), day)
        assumed = wins is None
        if wins is None:
            wins = [hrs.ASSUMED_WINDOW]
        if meal:
            rule = MEALS[meal]
            visit, earliest, latest = rule.visit_min, rule.earliest, rule.latest_start
        else:
            visit, earliest, latest = hrs.visit_minutes(place), 0, 1440
        weight = MOUNTAIN_WEIGHT if place.is_mountain and kind == "activity" else 1
        return _Item(place, kind, meal, must, visit, wins, assumed, earliest, latest, rank, weight)

    def fits(self, item: _Item) -> bool:
        start = hrs.earliest_start(item.wins, max(self.start_min, item.earliest), item.visit)
        return (
            start is not None and start <= item.latest_start and start + item.visit <= self.end_min
        )


# --- day assignment ---------------------------------------------------------------------
def _assign_activities(
    ctx: _Ctx,
    must: Sequence[Place],
    others: Sequence[Place],
    unplaced: List[Unplaced],
    avoid: Mapping[UUID, Set[int]],
    pinned: Optional[Mapping[UUID, date]] = None,
) -> List[List[_Item]]:
    n = len(ctx.dates)
    pinned = pinned or {}
    days: List[List[_Item]] = [[] for _ in range(n)]
    ordered: List[Tuple[Place, bool, int]] = [(p, True, -1) for p in must] + [
        (p, False, i) for i, p in enumerate(others)
    ]
    cap_total = n * ctx.cap

    def item_for(place: Place, d: int, is_must: bool, rank: int) -> _Item:
        return ctx.make_item(place, ctx.dates[d], "activity", is_must, rank)

    # 1. feasibility per day; must-haves with no feasible day are reported at once
    feasible: Dict[UUID, List[int]] = {}
    todo: List[Tuple[Place, bool, int]] = []
    for place, is_must, rank in ordered:
        days_ok = [d for d in range(n) if ctx.fits(item_for(place, d, is_must, rank))]
        pin = pinned.get(place.id)
        if pin is not None:  # Ш-61: a wish with a date is never moved to another day
            wanted = [d for d in days_ok if ctx.dates[d] == pin]
            if not wanted and is_must:
                feasible[place.id] = wanted
                reason = "closed_on_trip_days" if pin in ctx.dates else "no_time"
                unplaced.append(Unplaced(place, reason, True, pin))
                continue
            days_ok = wanted
        if not days_ok:
            feasible[place.id] = days_ok
            if is_must:
                unplaced.append(Unplaced(place, "closed_on_trip_days", True))
            continue
        if is_must and pin is None:  # a must-have that did not fit on a day tries the others
            days_ok = [d for d in days_ok if d not in avoid.get(place.id, ())] or days_ok
        feasible[place.id] = days_ok
        todo.append((place, is_must, rank))

    # 2. mountains first, one per day where possible, on the day with the driest morning
    load = [0] * n
    fixed: Set[UUID] = set()
    seeds: Dict[int, Point] = {}
    mountain_day: Dict[UUID, int] = {}
    for place, is_must, rank in todo:
        if not place.is_mountain:
            continue
        taken = set(mountain_day.values())
        choices = [d for d in feasible[place.id] if d not in taken] or feasible[place.id]
        d = min(choices, key=lambda x: (ctx.morning_rain(ctx.dates[x]), x))
        if load[d] + MOUNTAIN_WEIGHT > ctx.cap and not is_must and load[d] > 0:
            continue
        mountain_day[place.id] = d
        fixed.add(place.id)
        days[d].append(item_for(place, d, is_must, rank))
        load[d] += MOUNTAIN_WEIGHT
        seeds.setdefault(d, _pt(place))

    rest = [t for t in todo if t[0].id not in fixed]
    if not rest and not fixed:
        return days

    # 3. seeds for the other days: farthest-first from the already chosen seeds
    pool_pts = [_pt(p) for p, _, _ in rest[: max(1, cap_total)]]
    chosen: List[Point] = list(seeds.values())
    for d in range(n):
        if d in seeds:
            continue
        if not pool_pts:
            break
        ref = chosen or [ctx.start_point]
        far = max(
            range(len(pool_pts)),
            key=lambda i: (min(_dist_km(pool_pts[i], c) for c in ref), -i),
        )
        seeds[d] = pool_pts[far]
        chosen.append(pool_pts[far])

    centroids = {d: seeds[d] for d in seeds}

    def assign(centres: Dict[int, Point]) -> Tuple[List[List[_Item]], List[int]]:
        out: List[List[_Item]] = [list(days[d]) for d in range(n)]
        used = list(load)
        skipped_rain: List[Tuple[Place, bool, int]] = []

        def best_day(place, is_must, rank, relaxed):
            options = []
            for d in feasible[place.id]:
                if not centres.get(d):
                    continue
                full = used[d] + 1 > ctx.cap
                if full and not is_must:
                    continue
                outdoor_in_rain = (
                    (place.outdoor or place.setting == "outdoor")
                    and not is_must
                    and not relaxed
                    and ctx.rain_share(ctx.dates[d]) >= RAIN_DAY_SKIP
                )
                if outdoor_in_rain:
                    continue
                options.append((full, used[d] if is_must and full else 0,
                                _dist_km(_pt(place), centres[d]), d))  # fmt: skip
            return min(options)[3] if options else None

        for place, is_must, rank in rest:
            d = best_day(place, is_must, rank, False)
            if d is None:
                if not is_must and any(
                    ctx.rain_share(ctx.dates[x]) >= RAIN_DAY_SKIP for x in feasible[place.id]
                ):
                    skipped_rain.append((place, is_must, rank))
                continue
            out[d].append(item_for(place, d, is_must, rank))
            used[d] += 1
        for place, is_must, rank in skipped_rain:  # rain everywhere and room left: use them
            d = best_day(place, is_must, rank, True)
            if d is not None:
                out[d].append(item_for(place, d, is_must, rank))
                used[d] += 1
        return out, used

    result = days
    for _ in range(KMEANS_ITERATIONS):
        result, _used = assign(centroids)
        for d in range(n):
            pts = [_pt(i.place) for i in result[d]]
            if pts:
                centroids[d] = _centroid(pts, centroids.get(d, ctx.start_point))
    # a must-have that stayed out (no day could take it): put it on the lightest feasible day
    placed = {i.place.id for day in result for i in day}
    for place, is_must, rank in rest:
        if is_must and place.id not in placed:
            d = min(feasible[place.id], key=lambda x: (len(result[x]), x))
            result[d].append(item_for(place, d, is_must, rank))
    return result


# --- meals ------------------------------------------------------------------------------
def _assign_meals(
    ctx: _Ctx,
    days: List[List[_Item]],
    must_food: Sequence[Place],
    food: Sequence[Place],
    unplaced: List[Unplaced],
    warnings: List[LayoutWarning],
    avoid: Mapping[UUID, Set[int]],
    pinned: Optional[Mapping[UUID, date]] = None,
) -> None:
    n = len(ctx.dates)
    pinned = pinned or {}
    slots: Dict[Tuple[int, str], Optional[_Item]] = {(d, m): None for d in range(n) for m in MEALS}
    used: Set[UUID] = set()
    centres = [
        _centroid([_pt(i.place) for i in days[d] if i.kind == "activity"], ctx.start_point)
        for d in range(n)
    ]

    def meal_ok(place: Place) -> bool:
        return place.category not in NON_MEAL_CATEGORIES

    # must-have food: a meal slot if it fits one, else a plain stop (coffee, bakery, or no slot)
    for place in must_food:
        placed = False
        pin = pinned.get(place.id)
        pin_days = [d for d in range(n) if ctx.dates[d] == pin] if pin is not None else None
        if pin_days is not None and not pin_days:  # Ш-61: its day is not a day of this layout
            unplaced.append(Unplaced(place, "no_time", True, pin))
            continue
        if meal_ok(place):
            by_distance = sorted(range(n), key=lambda x: (_dist_km(_pt(place), centres[x]), x))
            if pin_days is not None:
                by_distance = pin_days
            skip = avoid.get(place.id, ()) if pin_days is None else ()
            for d in [x for x in by_distance if x not in skip] or by_distance:
                for meal in MEALS:
                    if slots[(d, meal)] is not None:
                        continue
                    item = ctx.make_item(place, ctx.dates[d], "meal", True, -1, meal)
                    if ctx.fits(item):
                        slots[(d, meal)] = item
                        used.add(place.id)
                        placed = True
                        break
                if placed:
                    break
        if placed:
            continue
        feasible = [
            d
            for d in range(n)
            if ctx.fits(ctx.make_item(place, ctx.dates[d], "activity", True, -1))
        ]
        if pin_days is not None:
            feasible = [d for d in feasible if d in pin_days]
        if not feasible:
            unplaced.append(Unplaced(place, "closed_on_trip_days", True))
            continue
        feasible = [d for d in feasible if d not in avoid.get(place.id, ())] or feasible
        d = min(feasible, key=lambda x: (len(days[x]), _dist_km(_pt(place), centres[x]), x))
        days[d].append(ctx.make_item(place, ctx.dates[d], "activity", True, -1))
        used.add(place.id)

    # ordinary meals: nearest to the day's centre first, the better-ranked food on ties
    for d in range(n):
        for meal in MEALS:
            if slots[(d, meal)] is not None:
                continue
            best: Optional[Tuple[float, int]] = None
            for rank, place in enumerate(food):
                if place.id in used or not meal_ok(place):
                    continue
                item = ctx.make_item(place, ctx.dates[d], "meal", False, rank, meal)
                if not ctx.fits(item):
                    continue
                key = (_dist_km(_pt(place), centres[d]) + 0.15 * rank, rank)
                if best is None or key < best:
                    best = key
            if best is None:
                warnings.append(LayoutWarning("meal_missing", ctx.dates[d], meal))
                continue
            place = food[best[1]]
            used.add(place.id)
            slots[(d, meal)] = ctx.make_item(place, ctx.dates[d], "meal", False, best[1], meal)
    for (d, _meal), item in sorted(slots.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if item is not None:
            days[d].append(item)


# --- order inside a day -----------------------------------------------------------------
@dataclass
class _Sim:
    violations: int
    first_violation: Optional[int]
    rain: int
    end: int
    starts: List[Optional[int]]


class _DayOrder:
    def __init__(self, ctx: _Ctx, day: date, tm: TravelTimes, idx: Dict[UUID, int]):
        self.ctx, self.day, self.tm, self.idx = ctx, day, tm, idx
        self.rainy = ctx.rain_hours(day)

    def simulate(self, order: Sequence[_Item]) -> _Sim:
        ctx = self.ctx
        t = ctx.start_min
        prev = 0  # point 0 is the day's start
        viol, first, rain = 0, None, 0
        starts: List[Optional[int]] = []
        for pos, item in enumerate(order):
            arrive = t + (
                self.tm.minutes(prev, self.idx[item.place.id]) + (BUFFER_MIN if pos else 0)
            )
            start = hrs.earliest_start(item.wins, max(arrive, item.earliest), item.visit)
            if start is None or start > item.latest_start or start + item.visit > ctx.end_min:
                viol += 1
                first = pos if first is None else first
                starts.append(None)
                continue
            if item.outdoor and any(
                h in self.rainy for h in range(start // 60, (start + item.visit - 1) // 60 + 1)
            ):
                rain += 1
            starts.append(start)
            t = start + item.visit
            prev = self.idx[item.place.id]
        return _Sim(viol, first, rain, t, starts)

    def key(self, order: Sequence[_Item]) -> Tuple[int, int, int]:
        sim = self.simulate(order)
        return (sim.violations, sim.rain, sim.end)

    def optimise(self, items: Sequence[_Item], fixed_first: Optional[_Item]) -> List[_Item]:
        activities = [i for i in items if i.kind == "activity" and i is not fixed_first]
        meals = sorted((i for i in items if i.kind == "meal"), key=lambda i: i.earliest)
        head = [fixed_first] if fixed_first else []
        # nearest neighbour over the activities, from the start (or the fixed first stop)
        order = list(head)
        left = sorted(activities, key=lambda i: i.place.id)
        prev = self.idx[head[0].place.id] if head else 0
        while left:
            nxt = min(
                left, key=lambda i: (self.tm.minutes(prev, self.idx[i.place.id]), str(i.place.id))
            )
            left.remove(nxt)
            order.append(nxt)
            prev = self.idx[nxt.place.id]
        for meal in meals:  # insert each meal where the day ends soonest
            best = None
            for pos in range(len(head), len(order) + 1):
                trial = order[:pos] + [meal] + order[pos:]
                k = self.key(trial)
                if best is None or k < best[0]:
                    best = (k, trial)
            order = best[1]
        # 2-opt and relocate on everything after the fixed head
        h = len(head)
        improved = True
        while improved:
            improved = False
            cur = self.key(order)
            for i in range(h, len(order) - 1):
                for j in range(i + 1, len(order)):
                    trial = order[:i] + order[i : j + 1][::-1] + order[j + 1 :]
                    k = self.key(trial)
                    if k < cur:
                        order, cur, improved = trial, k, True
            for i in range(h, len(order)):
                for j in range(h, len(order)):
                    if i == j:
                        continue
                    trial = order[:i] + order[i + 1 :]
                    trial = trial[:j] + [order[i]] + trial[j:]
                    k = self.key(trial)
                    if k < cur:
                        order, cur, improved = trial, k, True
        return order


def _fixed_first(items: Sequence[_Item]) -> Optional[_Item]:
    mountains = [i for i in items if i.kind == "activity" and i.place.is_mountain]
    if not mountains:
        return None
    return min(mountains, key=lambda i: (not i.must, -i.visit, i.rank, str(i.place.id)))


def _plan_order(
    ctx: _Ctx,
    day: date,
    items: List[_Item],
    tm: TravelTimes,
    idx: Dict[UUID, int],
    unplaced: List[Unplaced],
    warnings: List[LayoutWarning],
) -> List[_Item]:
    """Best order; while a stop does not fit, drop the least wanted one (never a must-have
    before every other optional activity is gone) and try again."""
    solver = _DayOrder(ctx, day, tm, idx)
    items = list(items)
    while True:
        order = solver.optimise(items, _fixed_first(items))
        sim = solver.simulate(order)
        if not sim.violations:
            return order
        bad = order[sim.first_violation]
        victim = bad
        if bad.must:
            optional = [i for i in items if not i.must and i.kind == "activity"]
            if optional:
                victim = max(optional, key=lambda i: (i.rank, str(i.place.id)))
        _drop(victim, items, day, unplaced, warnings)


def _drop(
    item: _Item,
    items: List[_Item],
    day: date,
    unplaced: List[Unplaced],
    warnings: List[LayoutWarning],
) -> None:
    items.remove(item)
    if item.kind == "meal" and not item.must:
        warnings.append(LayoutWarning("meal_missing", day, item.meal))
    else:
        unplaced.append(Unplaced(item.place, "no_time", item.must, day))


# --- timing with real legs --------------------------------------------------------------
def _at(day: date, minutes: int) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=default_region().tz) + timedelta(
        minutes=minutes
    )


async def _time_day(
    ctx: _Ctx,
    day: date,
    order: Sequence[_Item],
    tm: TravelTimes,
    idx: Dict[UUID, int],
    legs: LegProvider,
    explicit_start: bool,
    unplaced: List[Unplaced],
    warnings: List[LayoutWarning],
) -> DayPlan:
    plan = DayPlan(day)
    rainy = ctx.rain_hours(day)
    t = ctx.start_min
    prev_item: Optional[_Item] = None
    for item in order:
        origin_idx = idx[prev_item.place.id] if prev_item else 0
        dest = _pt(item.place)
        leg: Optional[Leg] = None
        if prev_item is not None or explicit_start:
            origin = _pt(prev_item.place) if prev_item else ctx.start_point
            depart = t + (BUFFER_MIN if prev_item else 0)
            options = await legs.options(origin, dest, _at(day, depart))
            default = pick_default(options)
            if default is not None:
                travel_s, estimated = leg_seconds(default), False
            else:
                travel_s, estimated = tm.minutes(origin_idx, idx[item.place.id]) * 60.0, True
            leg = Leg(
                prev_item.place.id if prev_item else None,
                item.place.id,
                _at(day, depart),
                options,
                default.mode if default else None,
                travel_s,
                estimated,
            )
            arrive = depart + int(-(-travel_s // 60))
        else:
            arrive = t + tm.minutes(origin_idx, idx[item.place.id])
        start = hrs.earliest_start(item.wins, max(arrive, item.earliest), item.visit)
        if start is None or start > item.latest_start or start + item.visit > ctx.end_min:
            _drop_late(item, day, unplaced, warnings)
            continue
        if leg is not None:
            plan.legs.append(leg)
        plan.stops.append(
            Stop(
                place=item.place,
                kind=item.kind,
                meal=item.meal,
                start=_at(day, start),
                end=_at(day, start + item.visit),
                visit_min=item.visit,
                must_have=item.must,
                hours_assumed=item.assumed,
                rain_exposed=item.outdoor
                and any(h in rainy for h in range(start // 60, (start + item.visit - 1) // 60 + 1)),
            )
        )
        t = start + item.visit
        prev_item = item
    return plan


def _drop_late(
    item: _Item, day: date, unplaced: List[Unplaced], warnings: List[LayoutWarning]
) -> None:
    if item.kind == "meal" and not item.must:
        warnings.append(LayoutWarning("meal_missing", day, item.meal))
    else:
        unplaced.append(Unplaced(item.place, "no_time", item.must, day))


# --- entry point ------------------------------------------------------------------------
MUST_HAVE_RETRIES = 3  # extra passes for must-haves that did not fit the day they were given


async def plan_days(
    dates: Sequence[date],
    pace: Optional[str],
    must_have_places: Sequence[Place],
    activities: Sequence[Place],
    food: Sequence[Place],
    hours: Mapping[UUID, hrs.HoursRows],
    travel: TravelMatrixProvider,
    legs: LegProvider,
    forecast: Optional[Forecast] = None,
    start_point: Optional[Point] = None,
    pinned: Optional[Mapping[UUID, date]] = None,
) -> TripLayout:
    """`activities` and `food` in rank order (best first, as Ш-33 returns them).

    `pinned` (Ш-61): place id -> the date of a wish with a date. Such a place stays on that day (or
    is reported in `unplaced`); it is never moved to another one.

    A must-have that is dropped for lack of time on its day (`no_time`) is retried: the whole
    layout is rebuilt with that day excluded for it, up to MUST_HAVE_RETRIES more passes, and
    the pass with the fewest unplaced must-haves wins (the first on a tie). The result is
    deterministic: the same input always gives the same plan.
    """
    avoid: Dict[UUID, Set[int]] = {}
    best: Optional[TripLayout] = None
    for _ in range(MUST_HAVE_RETRIES + 1):
        layout = await _plan_once(
            dates, pace, must_have_places, activities, food, hours, travel, legs, forecast,
            start_point, avoid, pinned,
        )  # fmt: skip
        if best is None or len(layout.must_have_unplaced) < len(best.must_have_unplaced):
            best = layout
        grew = False
        for item in layout.must_have_unplaced:
            if item.reason != "no_time" or item.date not in dates:
                continue
            days_tried = avoid.setdefault(item.place.id, set())
            index = list(dates).index(item.date)
            if index not in days_tried:
                days_tried.add(index)
                grew = True
        if not grew:
            break
    assert best is not None
    return best


async def _plan_once(
    dates: Sequence[date],
    pace: Optional[str],
    must_have_places: Sequence[Place],
    activities: Sequence[Place],
    food: Sequence[Place],
    hours: Mapping[UUID, hrs.HoursRows],
    travel: TravelMatrixProvider,
    legs: LegProvider,
    forecast: Optional[Forecast],
    start_point: Optional[Point],
    avoid: Mapping[UUID, Set[int]],
    pinned: Optional[Mapping[UUID, date]] = None,
) -> TripLayout:
    pace = pace if pace in DAY_START else scoring.DEFAULT_PACE
    ctx = _Ctx(
        dates=list(dates),
        start_min=DAY_START[pace],
        end_min=DAY_END[pace],
        cap=scoring.ACTIVITIES_PER_DAY[pace],
        hours=hours,
        forecast=forecast or UnknownForecast(),
        start_point=start_point or default_region().centre,
    )
    layout = TripLayout(
        days=[], start_point=ctx.start_point, start_point_default=start_point is None
    )
    must_ids = {p.id for p in must_have_places}
    must_other = [p for p in must_have_places if not p.is_food]
    must_food = [p for p in must_have_places if p.is_food]
    others = [p for p in activities if p.id not in must_ids]
    rest_food = [p for p in food if p.id not in must_ids]

    days = _assign_activities(ctx, must_other, others, layout.unplaced, avoid, pinned)
    _assign_meals(ctx, days, must_food, rest_food, layout.unplaced, layout.warnings, avoid, pinned)

    # one matrix for the whole trip: start point + every place that has a day
    places = {i.place.id: i.place for day in days for i in day}
    ids = sorted(places, key=str)
    idx = {pid: n + 1 for n, pid in enumerate(ids)}
    points: List[Point] = [ctx.start_point] + [_pt(places[pid]) for pid in ids]
    tm = await travel.build(points)

    for d, day in enumerate(ctx.dates):
        order = _plan_order(ctx, day, days[d], tm, idx, layout.unplaced, layout.warnings)
        plan = await _time_day(
            ctx, day, order, tm, idx, legs, start_point is not None,
            layout.unplaced, layout.warnings,
        )  # fmt: skip
        layout.days.append(plan)

    layout.travel_estimated = tm.estimated or any(
        leg.estimated for plan in layout.days for leg in plan.legs
    )
    if layout.travel_estimated:
        layout.warnings.append(LayoutWarning("travel_estimated"))
    assumed = sorted({s.place.id for p in layout.days for s in p.stops if s.hours_assumed}, key=str)
    if assumed:
        layout.warnings.append(LayoutWarning("hours_assumed", detail=str(len(assumed))))
    return layout


@dataclass(frozen=True)
class KeptStop:
    """A stop of an existing day in the order to keep (Ш-38 edits)."""

    place: Place
    kind: str  # "activity" | "meal"
    meal: Optional[str]
    must_have: bool


@dataclass
class RetimedDay:
    plan: DayPlan
    unplaced: List[Unplaced]  # stops that no longer fit (opening hours, end of the day)
    warnings: List[LayoutWarning]
    travel_estimated: bool


async def retime_day(
    day: date,
    pace: Optional[str],
    stops: Sequence[KeptStop],
    hours: Mapping[UUID, hrs.HoursRows],
    travel: TravelMatrixProvider,
    legs: LegProvider,
    forecast: Optional[Forecast] = None,
    start_point: Optional[Point] = None,
) -> RetimedDay:
    """Ш-38: time ONE day again with its stops in the given order (no re-planning of the trip).

    Used after an edit (a stop removed or replaced): the order the person saw is kept, transitions
    are rebuilt with real legs (Ш-22 options) and the stops are timed one after another from the
    start of the day. A stop that no longer fits (hours, end of the day) is dropped and reported
    in `unplaced`, a dropped must-have is never silent. Deterministic.
    """
    pace = pace if pace in DAY_START else scoring.DEFAULT_PACE
    ctx = _Ctx(
        dates=[day],
        start_min=DAY_START[pace],
        end_min=DAY_END[pace],
        cap=scoring.ACTIVITIES_PER_DAY[pace],
        hours=hours,
        forecast=forecast or UnknownForecast(),
        start_point=start_point or default_region().centre,
    )
    order = [
        ctx.make_item(s.place, day, s.kind, s.must_have, rank, s.meal)
        for rank, s in enumerate(stops)
    ]
    ids = sorted({s.place.id for s in stops}, key=str)
    idx = {pid: n + 1 for n, pid in enumerate(ids)}
    by_id = {s.place.id: s.place for s in stops}
    points: List[Point] = [ctx.start_point] + [_pt(by_id[pid]) for pid in ids]
    tm = await travel.build(points)
    unplaced: List[Unplaced] = []
    warnings: List[LayoutWarning] = []
    plan = await _time_day(
        ctx, day, order, tm, idx, legs, start_point is not None, unplaced, warnings
    )
    estimated = tm.estimated or any(leg.estimated for leg in plan.legs)
    return RetimedDay(plan, unplaced, warnings, estimated)


async def layout_selection(
    conn,
    selection,
    brief: Mapping,
    travel: TravelMatrixProvider,
    legs: LegProvider,
    forecast: Optional[Forecast] = None,
    start_point: Optional[Point] = None,
) -> TripLayout:
    """Ш-33 `Selection` + brief dates -> layout (what Ш-36 `build_trip` will call)."""
    must = selection.must_have_places
    acts = [c.place for c in selection.activities]
    food = [c.place for c in selection.food]
    hours = await hrs.load_hours(conn, [p.id for p in must + acts + food])
    start, end = brief["start_date"], brief["end_date"]
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return await plan_days(
        dates, brief.get("pace"), must, acts, food, hours, travel, legs, forecast, start_point
    )
