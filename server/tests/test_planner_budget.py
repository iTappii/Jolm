"""Ш-35: plan cost, lodging options and the two over-budget variants. No database: fixture
places from the layout tests, fake matrix and fake router (offline, deterministic)."""

from dataclasses import replace
from datetime import date
from uuid import uuid4

from app.planner import budget as bud
from app.planner.layout import plan_days
from app.planner.travel import HaversineMatrix
from tests.test_planner_layout import LATE, SAT, WEEK, World, dates, legs_provider, mk

PRICES = {  # entry (activities) / average check (food), tenge
    "Музей Кастеева": 8000, "Парк Горького": 0, "Кок-Тобе": 3000, "Монумент": 0,
    "Галерея": 12000, "Собор": 0, "Театр": 15000, "Зелёный базар": 0,
    "Музей инструментов": 6000, "ТРЦ Мега": 0, "Ботанический сад": 2000,
    "Чайхана": 4000, "Дастархан": 2500, "Бистро": 6000, "Хинкальная": 3500,
    "Ужин у Медеу": 9000, "Шанхай": 5000,
    "Площадь Республики": 0, "Набережная": 0, "Аллея": 0,
    "Столовая": 1500, "Пекарня-кафе": 1800, "Шашлычная": 2000,
}  # fmt: skip
ACTS = (
    "Музей Кастеева", "Парк Горького", "Кок-Тобе", "Монумент", "Галерея", "Собор", "Театр",
    "Зелёный базар", "Музей инструментов", "ТРЦ Мега", "Ботанический сад",
)  # fmt: skip
FOOD = (
    "Чайхана", "Дастархан", "Бистро", "Хинкальная", "Ужин у Медеу", "Столовая", "Пекарня-кафе",
    "Шашлычная",
)  # fmt: skip


def priced(world, name):
    place = world[name]
    kzt = PRICES[name]
    return (
        replace(place, avg_check_kzt=kzt) if place.is_food else replace(place, entry_price_kzt=kzt)
    )


class Case:
    """A 3-day normal trip with priced fixture places and a Ш-33 style score per candidate."""

    def __init__(self, must_names=("Музей Кастеева",)):
        self.world = World()
        self.add_cheap_alternatives()
        self.must = [priced(self.world, n) for n in must_names]
        must_ids = {p.id for p in self.must}
        names = ACTS + ("Площадь Республики", "Набережная", "Аллея")
        self.acts = [priced(self.world, n) for n in names if self.world[n].id not in must_ids]
        self.food = [priced(self.world, n) for n in FOOD]
        # earlier in the list = more valuable
        self.scores = {p.id: 100.0 - i for i, p in enumerate(self.acts + self.food)}
        self.dates = dates(SAT, 3)

    def add_cheap_alternatives(self):
        """Free and cheap places that are not in the plan by default: what `cheaper` swaps to."""
        for name, lat, lon, cat, parent, outdoor, hours in (
            ("Площадь Республики", 43.2389, 76.9455, "landmark", "sights", True, WEEK),
            ("Набережная", 43.2450, 76.9400, "park", "nature", True, WEEK),
            ("Аллея", 43.2500, 76.9500, "park", "nature", True, WEEK),
            ("Столовая", 43.2420, 76.9400, "cafe_european", "food", False, LATE),
            ("Пекарня-кафе", 43.2440, 76.9420, "cafe_kazakh", "food", False, LATE),
            ("Шашлычная", 43.2460, 76.9440, "cafe_caucasian", "food", False, LATE),
        ):
            place = mk(name, lat, lon, cat, parent, outdoor=outdoor, visit=40)
            self.world.by_name[name] = place
            self.world.hours[place.id] = hours

    async def replan(self, activities, meals):
        return await plan_days(
            self.dates, "normal", self.must, activities, meals, self.world.hours,
            HaversineMatrix(), legs_provider(),
        )  # fmt: skip

    def inputs(self):
        return bud.PlanInputs(self.acts, self.food, self.scores, self.replan)

    async def base(self):
        return await self.replan(self.acts, self.food)


def plan_for(lodging_needed=False, nights=2, places=()):
    return bud.choose_lodging(places, (43.24, 76.95), nights, needed=lodging_needed)


def stops(layout, kind=None, must=None):
    return [
        s
        for d in layout.days
        for s in d.stops
        if (kind is None or s.kind == kind) and (must is None or s.must_have == must)
    ]


# --- cost calculation ---------------------------------------------------------------------
async def test_plan_cost_is_entries_plus_checks_plus_transport_plus_lodging():
    case = Case()
    layout = await case.base()
    costs = bud.plan_costs(layout, lodging_kzt=14000)
    entries = sum(s.place.entry_price_kzt or 0 for s in stops(layout, "activity"))
    meals = sum(s.place.avg_check_kzt for s in stops(layout, "meal"))
    transport = sum(
        o.cost_kzt_max
        for d in layout.days
        for leg in d.legs
        for o in leg.options
        if o.mode == leg.default_mode
    )
    assert entries > 0 and meals > 0 and transport > 0  # the fixture really has all four parts
    assert (costs.entries, costs.meals, costs.transport, costs.events) == (
        entries, meals, transport, 0,
    )  # fmt: skip
    assert costs.lodging == 14000
    assert costs.total == 14000 + entries + meals + transport
    assert costs.meals_assumed == 0 and costs.entries_unknown == 0


async def test_missing_prices_use_the_documented_defaults_and_are_counted():
    case = Case()
    case.food = [replace(p, avg_check_kzt=None) for p in case.food]
    case.acts = [replace(p, entry_price_kzt=None) for p in case.acts]
    layout = await case.base()
    costs = bud.plan_costs(layout, 0)
    n_meals = len(stops(layout, "meal"))
    assert n_meals == 6
    assert costs.meals == n_meals * bud.ASSUMED_MEAL_KZT and costs.meals_assumed == n_meals
    assert costs.entries_unknown == len(stops(layout, "activity", must=False))
    assert costs.entries == 8000  # only the priced must-have museum


# --- lodging ------------------------------------------------------------------------------
def lodging(name, cat, lat, lon, price):
    return bud.LodgingPlace(uuid4(), name, None, cat, lat, lon, price)


HOTELS = [
    lodging("Хостел А", "hostel", 43.240, 76.950, 6000),
    lodging("Хостел Б", "hostel", 43.241, 76.951, 8000),
    lodging("Хостел В", "hostel", 43.300, 77.000, 5000),
    lodging("Отель А", "hotel", 43.239, 76.946, 40000),
    lodging("Отель Б", "hotel", 43.250, 76.940, None),  # no price: the hotel default
    lodging("Гостевой дом", "guest_house", 43.230, 76.930, 15000),
    lodging("Отель В", "hotel", 43.100, 76.800, 20000),
]


def test_lodging_known_is_not_counted_at_all():
    plan = plan_for(lodging_needed=False, nights=4, places=HOTELS)
    assert plan.options == [] and plan.cost() == 0 and not plan.price_assumed


def test_lodging_options_are_three_to_five_priced_by_nights_and_mixed_kinds():
    plan = plan_for(True, nights=3, places=HOTELS)
    assert 3 <= len(plan.options) <= 5
    assert {o.place.category for o in plan.options} >= {"hostel", "hotel"}
    for option in plan.options:
        expected = option.place.price_per_night_kzt or bud.ASSUMED_NIGHT_KZT[option.place.category]
        assert option.total == 3 * expected == 3 * option.price
        assert option.assumed == (option.place.price_per_night_kzt is None)
    assert [o.rank for o in plan.options] == list(range(1, len(plan.options) + 1))
    assert sum(o.recommended for o in plan.options) == 1 and plan.options[0].recommended
    assert plan.cost() == plan.recommended.total
    assert plan.cheapest.price == min(o.price for o in plan.options)
    far = next(p for p in HOTELS if p.name_ru == "Отель В")
    assert far.id not in {o.place.id for o in plan.options}  # far and not cheap: left out


def test_lodging_with_few_places_and_none_at_all():
    few = plan_for(True, nights=2, places=HOTELS[:2])
    assert len(few.options) == 2  # fewer than 3 only because the database has fewer
    none = plan_for(True, nights=2, places=[])
    assert none.options == [] and none.no_options
    assert none.cost() == 2 * bud.ASSUMED_NIGHT_KZT["hostel"] and none.price_assumed


def test_one_day_trip_has_no_night_to_pay_for():
    assert bud.trip_nights(date(2026, 12, 5), date(2026, 12, 5)) == 0
    assert bud.trip_nights(date(2026, 12, 5), date(2026, 12, 9)) == 4
    plan = plan_for(True, nights=0, places=HOTELS)
    assert plan.cost() == 0 and plan.options == []


# --- over budget --------------------------------------------------------------------------
async def over_budget_case(cut=6000, lodging_places=HOTELS, nights=2):
    case = Case()
    base = await case.base()
    plan = plan_for(True, nights, lodging_places)
    total = bud.plan_costs(base, plan.cost()).total
    return case, base, plan, total - cut


async def test_drop_variant_removes_the_least_valuable_costly_optionals_only():
    case, base, plan, budget = await over_budget_case(cut=10000)
    variant = await bud.drop_variant(case.inputs(), base, plan, budget)
    assert variant.feasible and variant.costs.total <= budget
    assert variant.removed
    # must-haves stay, and so does everything that does not cost money
    assert {s.place.id for s in stops(base, must=True)} <= {
        s.place.id for s in stops(variant.layout)
    }
    assert all(PRICES[p.name] > 0 for p in variant.removed)
    assert all(p.id not in {s.place.id for s in stops(variant.layout)} for p in variant.removed)
    # least valuable first: every kept costly optional is worth at least as much as any removed
    kept = [
        s.place for s in stops(variant.layout, "activity", must=False) if s.place.entry_price_kzt
    ]
    worst_kept = min((case.scores[p.id] for p in kept), default=None)
    if worst_kept is not None:
        assert all(case.scores[p.id] <= worst_kept for p in variant.removed)
    assert len(stops(variant.layout, "meal")) == len(stops(base, "meal"))  # meals are not dropped


async def test_cheaper_variant_swaps_for_cheaper_places_and_cheapest_lodging():
    case, base, plan, budget = await over_budget_case(cut=14000)
    variant = await bud.cheaper_variant(case.inputs(), base, plan, budget)
    assert variant.feasible and variant.costs.total <= budget
    assert variant.lodging is plan.cheapest
    assert variant.costs.lodging == plan.cheapest.total < plan.recommended.total or (
        plan.cheapest is plan.recommended
    )
    for old, new in variant.swaps:
        assert bud.place_cost(new)[0] < bud.place_cost(old)[0]
        assert old.id not in {s.place.id for s in stops(variant.layout)}
        assert new.id in {s.place.id for s in stops(variant.layout)}
    assert {s.place.id for s in stops(base, must=True)} <= {
        s.place.id for s in stops(variant.layout)
    }


async def test_cheaper_variant_replaces_meals_too():
    case = Case()
    case.acts = [replace(p, entry_price_kzt=0) for p in case.acts]  # only the meals cost money
    base = await case.base()
    plan = plan_for(False)
    budget = bud.plan_costs(base, 0).total - 4000
    variant = await bud.cheaper_variant(case.inputs(), base, plan, budget)
    assert variant.swaps and all(old.is_food and new.is_food for old, new in variant.swaps)
    assert variant.feasible and variant.costs.total <= budget
    assert variant.lodging is None  # nothing to switch: the tourist has lodging


async def test_must_haves_are_never_removed_even_when_they_alone_exceed_the_budget():
    case = Case(must_names=("Музей Кастеева", "Театр", "Галерея", "Шанхай"))
    base = await case.base()
    plan = plan_for(False)
    floor = bud.must_have_floor(base, plan)
    assert floor == 8000 + 15000 + 12000 + 5000
    budget = floor - 1000  # even the must-haves alone do not fit
    assert bud.plan_costs(base, 0).total > budget
    must_ids = {s.place.id for s in stops(base, must=True)}
    assert len(must_ids) == 4
    for make in (bud.drop_variant, bud.cheaper_variant):
        variant = await make(case.inputs(), base, plan, budget)
        assert not variant.feasible
        assert must_ids <= {s.place.id for s in stops(variant.layout)}  # still all there
        assert variant.costs.total > budget  # honest: not pretended to fit
        assert not any(p.id in must_ids for p in variant.removed)
        assert not any(old.id in must_ids for old, _ in variant.swaps)


async def test_floor_counts_the_cheapest_lodging():
    case = Case()
    base = await case.base()
    plan = plan_for(True, 2, HOTELS)
    assert bud.must_have_floor(base, plan) == 8000 + plan.cheapest.total


async def test_variants_are_deterministic():
    case, base, plan, budget = await over_budget_case(cut=12000)

    def key(v):
        return (
            v.costs.total,
            [p.id for p in v.removed],
            [(a.id, b.id) for a, b in v.swaps],
            [(s.place.id, s.start) for s in stops(v.layout)],
        )

    first = [
        key(await f(case.inputs(), base, plan, budget))
        for f in (bud.drop_variant, bud.cheaper_variant)
    ]
    second = [
        key(await f(case.inputs(), base, plan, budget))
        for f in (bud.drop_variant, bud.cheaper_variant)
    ]
    assert first == second
