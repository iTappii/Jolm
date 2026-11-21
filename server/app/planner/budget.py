"""Ш-35: trip cost, lodging options and the two over-budget variants (SSOT §5.2).

Money is integer tenge for ONE traveller (the brief has no party size) for the WHOLE trip.

Plan cost = lodging + entry prices + average checks for meals + transport + events (none yet).
- lodging: `has_accommodation` true -> 0. Otherwise nights x price per night of the recommended
  option, nights = end_date - start_date (a one-day trip has no night).
- entries: `entry_price_kzt` of every activity stop; NULL counts as 0 and is counted in
  `entries_unknown` (parks and monuments are usually free, but nobody checked).
- meals: `avg_check_kzt` of every meal stop (and of a food must-have placed as a plain stop);
  NULL uses ASSUMED_MEAL_KZT and is counted in `meals_assumed`.
- transport: the upper cost (`cost_kzt_max`) of the default option of every leg.
- OPEN: all the defaults above are working assumptions, see docs/adr/0003-open-defaults.md.

Over budget (SSOT §16.3, default of TECH_PLAN §2: show both, the person chooses):
- `drop_places`: remove the least valuable optional activities (lowest Ш-33 score first; free
  ones are kept because removing them saves nothing) until the plan fits.
- `cheaper`: switch to the cheapest lodging option and replace costly optional activities and
  meals with cheaper candidates from the same pools.
Must-have places are never removed or replaced. Both variants are real re-layouts, so legs,
times and opening hours stay valid; their cost is computed from the new layout, not estimated.
If even the must-haves do not fit (`must_haves_exceed_budget`) the report says so.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple
from uuid import UUID

from app.planner.layout import NON_MEAL_CATEGORIES, Leg, Stop, TripLayout
from app.planner.model import Place
from app.routing.base import Point
from app.routing.fake import haversine_m

log = logging.getLogger(__name__)

# OPEN(SSOT §16.2/§5.2): defaults for missing prices, tenge per person.
ASSUMED_MEAL_KZT = 3000
ASSUMED_NIGHT_KZT: Dict[str, int] = {"hostel": 7000, "guest_house": 20000, "hotel": 35000}
DEFAULT_NIGHT_KZT = 20000  # accommodation of an unknown category
LODGING_MIN_OPTIONS = 3
LODGING_MAX_OPTIONS = 5
KM_PER_10K_KZT = 1.0  # lodging score = km to the plan's centre + price / 10 000 (lower is better)
MAX_ROUNDS = 6  # re-layouts per variant


def trip_nights(start: date, end: date) -> int:
    return max(0, (end - start).days)


# --- costs ------------------------------------------------------------------------------
def stop_cost(stop: Stop) -> Tuple[int, bool]:
    """(tenge, assumed). Meals and food stops use the average check; others the entry price."""
    return place_cost(stop.place, stop.kind == "meal")


def place_cost(place: Place, as_meal: Optional[bool] = None) -> Tuple[int, bool]:
    meal = place.is_food if as_meal is None else (as_meal or place.is_food)
    if meal:
        if place.avg_check_kzt is None:
            return ASSUMED_MEAL_KZT, True
        return int(place.avg_check_kzt), False
    if place.entry_price_kzt is None:
        return 0, True
    return int(place.entry_price_kzt), False


def leg_cost(leg: Leg) -> int:
    """Upper cost of the default option; 0 when no option was computed (a straight-line leg)."""
    for option in leg.options:
        if option.mode == leg.default_mode:
            return int(option.cost_kzt_max)
    return 0


@dataclass
class Costs:
    lodging: int = 0
    entries: int = 0
    meals: int = 0
    transport: int = 0
    events: int = 0  # Ф16
    meals_assumed: int = 0
    entries_unknown: int = 0

    @property
    def total(self) -> int:
        return self.lodging + self.entries + self.meals + self.transport + self.events

    @property
    def activities_total(self) -> int:
        return self.total - self.lodging


def plan_costs(layout: TripLayout, lodging_kzt: int) -> Costs:
    costs = Costs(lodging=lodging_kzt)
    for day in layout.days:
        for stop in day.stops:
            kzt, assumed = stop_cost(stop)
            if stop.kind == "meal" or stop.place.is_food:
                costs.meals += kzt
                costs.meals_assumed += 1 if assumed else 0
            else:
                costs.entries += kzt
                costs.entries_unknown += 1 if assumed else 0
        costs.transport += sum(leg_cost(leg) for leg in day.legs)
    return costs


# --- lodging ----------------------------------------------------------------------------
@dataclass(frozen=True)
class LodgingPlace:
    id: UUID
    name_ru: Optional[str]
    name_en: Optional[str]
    category: Optional[str]
    lat: float
    lon: float
    price_per_night_kzt: Optional[int]


def lodging_from_row(row: Mapping[str, Any]) -> LodgingPlace:
    price = row["price_per_night_kzt"]
    return LodgingPlace(
        row["id"], row["name_ru"], row["name_en"], row["category"], row["lat"], row["lon"],
        int(price) if price is not None else None,
    )  # fmt: skip


@dataclass
class LodgingOption:
    place: LodgingPlace
    price: int
    assumed: bool
    total: int
    distance_km: float
    score: float
    rank: int = 0
    recommended: bool = False


@dataclass
class LodgingPlan:
    needed: bool
    nights: int
    options: List[LodgingOption] = field(default_factory=list)

    @property
    def recommended(self) -> Optional[LodgingOption]:
        return next((o for o in self.options if o.recommended), None)

    @property
    def cheapest(self) -> Optional[LodgingOption]:
        return min(self.options, key=lambda o: (o.price, o.score, str(o.place.id)), default=None)

    @property
    def no_options(self) -> bool:
        return self.needed and self.nights > 0 and not self.options

    def cost(self, option: Optional[LodgingOption] = None) -> int:
        """Stay cost counted in the budget: the chosen option, else the recommended one, else
        (no option in the database) nights x the hostel default."""
        if not self.needed or self.nights == 0:
            return 0
        option = option or self.recommended
        if option is not None:
            return option.total
        return self.nights * ASSUMED_NIGHT_KZT["hostel"]

    @property
    def price_assumed(self) -> bool:
        if not self.needed or self.nights == 0:
            return False
        rec = self.recommended
        return True if rec is None else rec.assumed


def night_price(place: LodgingPlace) -> Tuple[int, bool]:
    if place.price_per_night_kzt is not None:
        return place.price_per_night_kzt, False
    return ASSUMED_NIGHT_KZT.get(place.category or "", DEFAULT_NIGHT_KZT), True


def choose_lodging(
    places: Sequence[LodgingPlace], centre: Point, nights: int, needed: bool
) -> LodgingPlan:
    """3-5 options by price and location (lower `km + price / 10 000` is better).

    Round-robin over the categories (hostel, hotel, guest house) so the person sees different
    kinds of places, then ordered by score; the best-scoring one is `recommended` and is the one
    counted in the budget. Fewer than 3 are returned only when the database has fewer.
    """
    plan = LodgingPlan(needed=needed, nights=nights)
    if not needed or nights == 0:
        return plan
    scored: List[LodgingOption] = []
    for place in places:
        price, assumed = night_price(place)
        km = haversine_m(centre, (place.lat, place.lon)) / 1000.0
        score = km + price / 10_000.0 * KM_PER_10K_KZT
        scored.append(LodgingOption(place, price, assumed, nights * price, km, score))
    scored.sort(key=lambda o: (o.score, str(o.place.id)))
    groups: Dict[str, List[LodgingOption]] = {}
    for option in scored:
        groups.setdefault(option.place.category or "", []).append(option)
    order = sorted(groups, key=lambda g: (groups[g][0].score, g))
    chosen: List[LodgingOption] = []
    depth = 0
    while len(chosen) < LODGING_MAX_OPTIONS and any(depth < len(groups[g]) for g in order):
        for g in order:
            if depth < len(groups[g]) and len(chosen) < LODGING_MAX_OPTIONS:
                chosen.append(groups[g][depth])
        depth += 1
    chosen.sort(key=lambda o: (o.score, str(o.place.id)))
    for rank, option in enumerate(chosen, start=1):
        option.rank = rank
    if chosen:
        chosen[0].recommended = True
    plan.options = chosen
    return plan


def layout_centre(layout: TripLayout) -> Point:
    pts = [(s.place.lat, s.place.lon) for d in layout.days for s in d.stops]
    if not pts:
        return layout.start_point
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


# --- variants ---------------------------------------------------------------------------
Replan = Callable[[Sequence[Place], Sequence[Place]], Awaitable[TripLayout]]


@dataclass
class PlanInputs:
    """What the variants need to re-run the layout without the Ш-33 selection."""

    activities: List[Place]  # the pool, best first
    food: List[Place]
    scores: Mapping[UUID, float]  # Ш-33 score by place id (value of a place)
    replan: Replan  # (activities, food) -> TripLayout; must-haves and dates are bound in


@dataclass
class Variant:
    kind: str  # "drop_places" | "cheaper"
    layout: TripLayout
    costs: Costs
    feasible: bool
    removed: List[Place] = field(default_factory=list)
    swaps: List[Tuple[Place, Place]] = field(default_factory=list)  # (replaced, replacement)
    lodging: Optional[LodgingOption] = None  # the option whose cost the variant counts


def _score(inputs: PlanInputs, place: Place) -> float:
    return inputs.scores.get(place.id, 0.0)


def _optional_stops(layout: TripLayout, kind: str) -> List[Stop]:
    return [s for d in layout.days for s in d.stops if s.kind == kind and not s.must_have]


def _leg_into(layout: TripLayout) -> Dict[UUID, int]:
    out: Dict[UUID, int] = {}
    for day in layout.days:
        for leg in day.legs:
            out[leg.destination_place_id] = leg_cost(leg)
    return out


def _in_pool_order(pool: Sequence[Place], keep: Set[UUID]) -> List[Place]:
    return [p for p in pool if p.id in keep]


# OPEN(SSOT §16.3): both variants are built and the person chooses (TECH_PLAN §2 default).
async def drop_variant(
    inputs: PlanInputs, base: TripLayout, plan: LodgingPlan, budget: int
) -> Variant:
    """Remove the least valuable optional activities that cost money until the plan fits."""
    lodging = plan.cost()
    layout = base
    removed: Dict[UUID, Place] = {}
    keep = {s.place.id for s in _optional_stops(base, "activity")}
    # the meals stay as they are: only the activities are given up (the day centres may move)
    meals = _in_pool_order(inputs.food, {s.place.id for s in _optional_stops(base, "meal")})
    for _ in range(MAX_ROUNDS):
        costs = plan_costs(layout, lodging)
        short = costs.total - budget
        if short <= 0:
            break
        into = _leg_into(layout)
        options = []
        for stop in _optional_stops(layout, "activity"):
            saving = place_cost(stop.place, False)[0] + into.get(stop.place.id, 0)
            if place_cost(stop.place, False)[0] > 0:
                options.append(
                    (_score(inputs, stop.place), -saving, str(stop.place.id), stop, saving)
                )
        if not options:
            break
        options.sort(key=lambda o: o[:3])
        saved = 0
        for *_k, stop, saving in options:
            removed[stop.place.id] = stop.place
            keep.discard(stop.place.id)
            saved += saving
            if saved >= short:
                break
        layout = await inputs.replan(_in_pool_order(inputs.activities, keep), meals)
    costs = plan_costs(layout, lodging)
    return Variant(
        "drop_places", layout, costs, costs.total <= budget,
        removed=[p for pid, p in removed.items() if pid not in _placed_ids(layout)],
    )  # fmt: skip


def _placed_ids(layout: TripLayout) -> Set[UUID]:
    return {s.place.id for d in layout.days for s in d.stops}


async def cheaper_variant(
    inputs: PlanInputs, base: TripLayout, plan: LodgingPlan, budget: int
) -> Variant:
    """Cheapest lodging, then cheaper replacements for the costly optional stops."""
    lodging_option = plan.cheapest
    if lodging_option is not None and plan.recommended is not None:
        if lodging_option.total >= plan.recommended.total:
            lodging_option = plan.recommended
    lodging = plan.cost(lodging_option)
    layout = base
    acts_keep = _in_pool_order(
        inputs.activities, {s.place.id for s in _optional_stops(base, "activity")}
    )
    food_keep = _in_pool_order(inputs.food, {s.place.id for s in _optional_stops(base, "meal")})
    swaps: Dict[UUID, Tuple[Place, Place]] = {}  # replacement id -> (replaced, replacement)
    seen: Set[UUID] = {p.id for p in acts_keep + food_keep}
    must_ids = {s.place.id for d in base.days for s in d.stops if s.must_have}
    for _ in range(MAX_ROUNDS):
        costs = plan_costs(layout, lodging)
        short = costs.total - budget
        if short <= 0:
            break
        costly = [
            (place_cost(s.place, s.kind == "meal")[0], s)
            for s in _optional_stops(layout, "activity") + _optional_stops(layout, "meal")
        ]
        costly.sort(key=lambda c: (-c[0], str(c[1].place.id)))
        saved, changed = 0, False
        for cost, stop in costly:
            if cost <= 0:
                break
            repl = _cheaper_replacement(inputs, stop, cost, seen | must_ids)
            if repl is None:
                continue
            seen.add(repl.id)
            changed = True
            saved += cost - place_cost(repl, stop.kind == "meal")[0]
            bucket = acts_keep if stop.kind == "activity" else food_keep
            bucket[:] = [repl if p.id == stop.place.id else p for p in bucket]
            origin = swaps.pop(stop.place.id, (stop.place, repl))[0]  # swapped again: keep origin
            swaps[repl.id] = (origin, repl)
            if saved >= short:
                break
        if not changed:
            break
        layout = await inputs.replan(acts_keep, food_keep)
    costs = plan_costs(layout, lodging)
    placed = _placed_ids(layout)
    return Variant(
        "cheaper", layout, costs, costs.total <= budget,
        swaps=[pair for rid, pair in swaps.items() if rid in placed and pair[0].id not in placed],
        lodging=lodging_option,
    )  # fmt: skip


def _cheaper_replacement(
    inputs: PlanInputs, stop: Stop, cost: int, taken: Set[UUID]
) -> Optional[Place]:
    meal = stop.kind == "meal"
    pool = inputs.food if meal else inputs.activities
    best: Optional[Tuple[Tuple[bool, float, str], Place]] = None
    for place in pool:
        if place.id in taken or place.id == stop.place.id:
            continue
        if meal and place.category in NON_MEAL_CATEGORIES:
            continue
        if not meal and place.is_mountain and not stop.place.is_mountain:
            continue  # a mountain trip is a day of its own, not a cheap filler
        if place_cost(place, meal)[0] >= cost:
            continue
        key = (place.parent != stop.place.parent, -_score(inputs, place), str(place.id))
        if best is None or key < best[0]:
            best = (key, place)
    return best[1] if best else None


# --- report -----------------------------------------------------------------------------
def must_have_floor(layout: TripLayout, plan: LodgingPlan) -> int:
    """Least the plan can cost: must-have entries and meals + the cheapest lodging. A lower
    bound (no transport), so `floor > budget` is certain, not a guess."""
    floor = 0
    for day in layout.days:
        for stop in day.stops:
            if stop.must_have:
                floor += stop_cost(stop)[0]
    cheapest = plan.cheapest
    return floor + plan.cost(cheapest)
