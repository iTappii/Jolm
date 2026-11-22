"""Ш-34: day layout on reference briefs. Pure places + fake matrix (no database), one database
test through Ш-33, one integration test with a real Valhalla when it is reachable."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from app.places.service import is_open_now
from app.planner import hours as hrs
from app.planner import layout
from app.planner.candidates import select_candidates
from app.planner.layout import MEALS, plan_days
from app.planner.model import Place
from app.planner.travel import (
    DirectionsLegs,
    HaversineMatrix,
    RouterMatrix,
    pick_default,
)
from app.planner.weather import UnknownForecast
from app.regions import default_region
from app.routing import FakeRouter, RoutingUnavailable
from app.routing.costs import Tariff
from app.routing.schemas import DirectionOption
from tests.test_places import add_place, load_categories
from tests.test_routing import VALHALLA, needs_valhalla

TARIFFS = {
    "car": Tariff("car", Decimal(0), Decimal(0), Decimal(75)),
    "taxi": Tariff("taxi", Decimal(500), Decimal(0), Decimal(0)),
    "scooter": Tariff("scooter", Decimal(100), Decimal(30), Decimal(0)),
}
WEEK = [(wd, time(9, 0), time(20, 0)) for wd in range(7)]
LATE = [(wd, time(10, 0), time(23, 0)) for wd in range(7)]
SAT = date(2026, 12, 5)
MON = date(2026, 12, 7)


def dates(start: date, n: int) -> List[date]:
    return [start + timedelta(days=i) for i in range(n)]


def mk(name, lat, lon, category, parent, *, outdoor=False, mountain=False, visit=None, pop=50):
    return Place(
        id=uuid4(), name_ru=name, name_en=None, category=category, parent=parent, kind="poi",
        setting="outdoor" if outdoor else "indoor", outdoor=outdoor, lat=lat, lon=lon,
        popularity=pop, is_public=True, is_mountain=mountain, typical_visit_min=visit,
        entry_price_kzt=None, avg_check_kzt=None,
    )  # fmt: skip


class World:
    """Fixture places around Almaty, with hours."""

    def __init__(self):
        self.hours: Dict[UUID, list] = {}
        self.by_name: Dict[str, Place] = {}
        rows = [
            # name, lat, lon, category, parent, outdoor, mountain, visit, hours
            ("Музей Кастеева", 43.2570, 76.9535, "museum", "culture", False, False, 90, WEEK),
            ("Музей инструментов", 43.2570, 76.9390, "museum", "culture", False, False, None, WEEK),
            ("Музей закрыт по понедельникам", 43.2520, 76.9460, "museum", "culture", False, False,
             90,
             [(wd, time(10, 0), time(18, 0)) for wd in range(1, 7)]),
            ("Галерея", 43.2480, 76.9500, "gallery", "culture", False, False, 60, WEEK),
            ("Парк Горького", 43.2540, 76.9565, "park", "nature", True, False, 60, None),
            ("Кок-Тобе", 43.2330, 76.9747, "viewpoint", "nature", True, False, 45, WEEK),
            ("Монумент", 43.2380, 76.9450, "monument", "sights", True, False, 20, None),
            ("Ботанический сад", 43.2200, 76.9200, "garden", "nature", True, False, 90, WEEK),
            ("Зелёный базар", 43.2610, 76.9560, "market", "shopping", False, False, 60, WEEK),
            ("ТРЦ Мега", 43.2020, 76.8930, "mall", "shopping", False, False, 90, LATE),
            ("Театр", 43.2500, 76.9400, "theatre", "culture", False, False, 120, WEEK),
            ("Собор", 43.2590, 76.9540, "religious", "sights", False, False, 30, WEEK),
            ("Медеу", 43.1573, 77.0587, "mountain", "nature", True, True, 180, WEEK),
            ("Бутаковка", 43.1400, 76.9400, "mountain", "nature", True, True, 150, WEEK),
            ("Чайхана", 43.2400, 76.9300, "cafe_oriental", "food", False, False, None, LATE),
            ("Дастархан", 43.2410, 76.9310, "cafe_kazakh", "food", False, False, None, LATE),
            ("Шанхай", 43.2420, 76.9320, "cafe_chinese", "food", False, False, None, LATE),
            ("Хинкальная", 43.2540, 76.9500, "cafe_caucasian", "food", False, False, None, LATE),
            ("Бистро", 43.2500, 76.9450, "cafe_european", "food", False, False, None, LATE),
            ("Ужин у Медеу", 43.1600, 77.0500, "restaurant", "food", False, False, None, LATE),
            ("Кофейня", 43.2430, 76.9330, "coffee", "food", False, False, 30, LATE),
        ]  # fmt: skip
        for name, lat, lon, cat, parent, outdoor, mountain, visit, hours in rows:
            p = mk(name, lat, lon, cat, parent, outdoor=outdoor, mountain=mountain, visit=visit)
            self.by_name[name] = p
            if hours is not None:
                self.hours[p.id] = hours

    def __getitem__(self, name: str) -> Place:
        return self.by_name[name]

    def pick(self, *names: str) -> List[Place]:
        return [self.by_name[n] for n in names]


class Rain:
    def __init__(self, rainy_days, from_h=0, to_h=24):
        self.days, self.from_h, self.to_h = set(rainy_days), from_h, to_h

    def rain_probability(self, day, hour):
        if day in self.days:
            return 0.9 if self.from_h <= hour < self.to_h else 0.0
        return 0.0


def legs_provider():
    return DirectionsLegs(FakeRouter(), None, TARIFFS)


async def run(world, dts, pace, must, acts, food, forecast=None, start_point=None, hours=None):
    return await plan_days(
        dts, pace, must, acts, food, world.hours if hours is None else hours,
        HaversineMatrix(), legs_provider(), forecast, start_point,
    )  # fmt: skip


def slot_minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def check_invariants(plan, world_hours, pace):
    seen = set()
    for day in plan.days:
        d = day.date
        prev_end: Optional[datetime] = None
        assert len(day.legs) == max(0, len(day.stops) - 1)  # default start: no start leg
        for i, stop in enumerate(day.stops):
            assert stop.place.id not in seen, "a place is planned twice"
            seen.add(stop.place.id)
            assert stop.start >= _at(d, layout.DAY_START[pace])
            assert stop.end <= _at(d, layout.DAY_END[pace])
            assert stop.end - stop.start == timedelta(minutes=stop.visit_min)
            wins = hrs.windows(world_hours.get(stop.place.id), d)
            if wins is None:
                wins = [hrs.ASSUMED_WINDOW]
                assert stop.hours_assumed
            assert any(
                a <= slot_minutes(stop.start) and slot_minutes(stop.end) <= b for a, b in wins
            ), (stop.place.name, d, stop.start, wins)
            if stop.kind == "meal":
                rule = MEALS[stop.meal]
                assert rule.earliest <= slot_minutes(stop.start) <= rule.latest_start
            if prev_end is not None:
                leg = day.legs[i - 1]
                assert leg.destination_place_id == stop.place.id
                assert leg.origin_place_id == day.stops[i - 1].place.id
                gap = (stop.start - prev_end).total_seconds()
                assert gap >= leg.travel_s + layout.BUFFER_MIN * 60, "overlap"
                assert leg.options and leg.default_mode
                assert leg.default_mode in {o.mode for o in leg.options}
            prev_end = stop.end


def _at(d, minutes):
    return layout._at(d, minutes)


def names(day):
    return [s.place.name for s in day.stops]


# --- reference briefs -------------------------------------------------------------------
async def test_one_day_calm():
    w = World()
    acts = w.pick("Музей Кастеева", "Парк Горького", "Кок-Тобе", "Монумент", "Галерея", "Собор")
    food = w.pick("Чайхана", "Дастархан", "Бистро")
    plan = await run(w, [SAT], "calm", [], acts, food)
    check_invariants(plan, w.hours, "calm")
    day = plan.days[0]
    activities = [s for s in day.stops if s.kind == "activity"]
    meals = [s for s in day.stops if s.kind == "meal"]
    assert len(activities) == 3  # calm = 3 activities
    assert sorted(m.meal for m in meals) == ["dinner", "lunch"]
    assert not plan.unplaced and not plan.must_have_unplaced
    assert plan.start_point_default
    # same input, same plan
    again = await run(w, [SAT], "calm", [], acts, food)
    assert [(s.place.id, s.start) for s in again.days[0].stops] == [
        (s.place.id, s.start) for s in day.stops
    ]


async def test_three_days_normal_with_cuisine_must_have():
    w = World()
    must = w.pick("Шанхай", "Музей Кастеева")
    acts = w.pick(
        "Парк Горького", "Кок-Тобе", "Монумент", "Галерея", "Собор", "Зелёный базар", "Театр",
        "Музей инструментов", "Ботанический сад", "ТРЦ Мега", "Медеу",
    )  # fmt: skip
    food = w.pick("Чайхана", "Дастархан", "Хинкальная", "Бистро", "Ужин у Медеу")
    plan = await run(w, dates(SAT, 3), "normal", must, acts, food)
    check_invariants(plan, w.hours, "normal")
    placed = {s.place.id: s for day in plan.days for s in day.stops}
    assert w["Шанхай"].id in placed and placed[w["Шанхай"].id].kind == "meal"
    assert w["Музей Кастеева"].id in placed
    assert not plan.must_have_unplaced
    for day in plan.days:
        assert sorted(s.meal for s in day.stops if s.kind == "meal") == ["dinner", "lunch"]
        assert len([s for s in day.stops if s.kind == "activity"]) <= 4
    # clusters: the mountain does not share a day with the far mall
    for day in plan.days:
        assert not ({"Медеу", "ТРЦ Мега"} <= set(names(day)))


async def test_five_days_dense_mountain_monday_closed_and_rain():
    w = World()
    days5 = dates(MON, 5)  # Mon..Fri
    rainy = {days5[0], days5[1], days5[3]}  # day 1, 2, 4 rain all day; day 3 and 5 dry
    must = w.pick("Музей закрыт по понедельникам", "Медеу", "Чайхана")
    acts = w.pick(
        "Парк Горького", "Кок-Тобе", "Монумент", "Галерея", "Собор", "Зелёный базар", "Театр",
        "Музей Кастеева", "Музей инструментов", "Ботанический сад", "ТРЦ Мега", "Бутаковка",
    )  # fmt: skip
    food = w.pick("Дастархан", "Хинкальная", "Бистро", "Шанхай", "Ужин у Медеу")
    plan = await run(w, days5, "dense", must, acts, food, forecast=Rain(rainy))
    check_invariants(plan, w.hours, "dense")
    assert not plan.must_have_unplaced
    where = {s.place.name: day.date for day in plan.days for s in day.stops}
    assert where["Музей закрыт по понедельникам"] != MON  # closed on Mondays
    assert where["Медеу"] not in rainy  # driest morning
    medeu_day = next(d for d in plan.days if d.date == where["Медеу"])
    assert medeu_day.stops[0].place.name == "Медеу"  # mountain first thing in the day
    assert medeu_day.stops[0].start.hour <= 10
    assert "Чайхана" in where
    # rain: no outdoor stop in rain while dry days existed to hold it
    for day in plan.days:
        for s in day.stops:
            if day.date in rainy:
                assert not (s.place.outdoor and not s.must_have), (day.date, s.place.name)
            assert not s.rain_exposed or s.must_have
    for day in plan.days:
        assert len([s for s in day.stops if s.kind == "activity"]) <= 6


async def test_unknown_forecast_puts_mountain_first_in_the_morning():
    w = World()
    plan = await run(
        w, dates(SAT, 2), "normal", w.pick("Медеу"), w.pick("Галерея", "Собор"),
        w.pick("Чайхана", "Дастархан", "Бистро", "Хинкальная"),
    )  # fmt: skip
    check_invariants(plan, w.hours, "normal")
    first = plan.days[0].stops[0]
    assert first.place.name == "Медеу" and first.start.hour * 60 + first.start.minute <= 11 * 60


async def test_mountains_get_separate_days_and_best_forecast():
    w = World()
    days3 = dates(SAT, 3)
    plan = await run(
        w, days3, "normal", w.pick("Медеу", "Бутаковка"), w.pick("Галерея", "Собор"),
        w.pick("Чайхана", "Дастархан", "Бистро", "Хинкальная", "Шанхай", "Ужин у Медеу"),
        forecast=Rain({days3[0]}),
    )  # fmt: skip
    where = {s.place.name: d.date for d in plan.days for s in d.stops}
    assert where["Медеу"] != where["Бутаковка"]
    assert days3[0] not in (where["Медеу"], where["Бутаковка"])


async def test_must_have_closed_on_all_trip_days_is_reported():
    w = World()
    only_sunday = mk("Музей по воскресеньям", 43.25, 76.95, "museum", "culture", visit=60)
    w.hours[only_sunday.id] = [(6, time(10, 0), time(17, 0))]
    plan = await run(
        w, dates(MON, 2), "normal", [only_sunday], w.pick("Галерея"), w.pick("Чайхана", "Бистро")
    )
    assert [(u.place.id, u.reason) for u in plan.must_have_unplaced] == [
        (only_sunday.id, "closed_on_trip_days")
    ]
    assert all(s.place.id != only_sunday.id for d in plan.days for s in d.stops)


async def test_must_have_beyond_capacity_is_kept_and_overflow_reported_honestly():
    w = World()
    must = w.pick("Музей Кастеева", "Музей инструментов", "Галерея", "Театр", "Собор", "Монумент")
    plan = await run(w, [SAT], "calm", must, [], w.pick("Чайхана", "Бистро"))
    check_invariants(plan, w.hours, "calm")
    placed = {s.place.id for s in plan.days[0].stops}
    unplaced = {u.place.id for u in plan.must_have_unplaced}
    # every must-have is either in the plan or reported, never lost
    assert {p.id for p in must} == (placed & {p.id for p in must}) | unplaced
    assert all(u.reason == "no_time" for u in plan.must_have_unplaced)


async def test_past_midnight_hours_and_coffee_must_have():
    w = World()
    bar = mk("Бар до двух", 43.25, 76.95, "bar", "food", visit=90)
    w.hours[bar.id] = [(wd, time(18, 0), time(2, 0)) for wd in range(7)]
    plan = await run(
        w, [SAT], "dense", [bar, w["Кофейня"]], w.pick("Галерея"), w.pick("Чайхана", "Бистро")
    )
    check_invariants(plan, w.hours, "dense")
    stops = {s.place.name: s for s in plan.days[0].stops}
    assert stops["Бар до двух"].kind == "activity" and stops["Бар до двух"].start.hour >= 18
    assert stops["Кофейня"].kind == "activity"  # coffee is a stop, never a meal


def test_windows_and_open_now_agree():
    rows = [
        (4, time(18, 0), time(2, 0)),
        (5, time(0, 0), time(23, 59)),
        (6, time(9, 0), time(18, 0)),
    ]
    for day in dates(date(2026, 12, 4), 7):
        for minute in range(0, 1440, 30):
            wins = hrs.windows(rows, day)
            mine = any(a <= minute < b for a, b in wins)
            now = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=default_region().tz)
            assert mine == is_open_now(rows, now), (day, minute)


def test_visit_minutes_defaults():
    p = mk("x", 43.2, 76.9, "museum", "culture")
    assert hrs.visit_minutes(p) == 90
    assert hrs.visit_minutes(mk("m", 43.2, 76.9, "mountain", "nature", mountain=True)) == 180
    assert hrs.visit_minutes(mk("z", 43.2, 76.9, None, None)) == 60
    assert hrs.visit_minutes(mk("v", 43.2, 76.9, "museum", "culture", visit=20)) == 20


# --- legs, matrix, fallbacks ------------------------------------------------------------
async def test_default_leg_is_the_recommended_option():
    w = World()
    plan = await run(w, [SAT], "normal", [], w.pick("Музей Кастеева", "Собор", "Галерея"),
                     w.pick("Чайхана", "Бистро"))  # fmt: skip
    for leg in plan.days[0].legs:
        flagged = [o for o in leg.options if o.recommended]
        assert len(flagged) == 1 and flagged[0].mode == leg.default_mode
    # close stops are walked (<= 15 min), distant ones are not
    short = DirectionOption(mode="walk", duration_s=600, distance_m=800, cost_kzt_min=0,
                            cost_kzt_max=0, geometry="", approximate=False)  # fmt: skip
    taxi = DirectionOption(mode="taxi", duration_s=300, distance_m=800, cost_kzt_min=500,
                           cost_kzt_max=500, geometry="", approximate=True)  # fmt: skip
    assert pick_default([taxi, short]).mode == "walk"
    assert pick_default([]) is None


class DownRouter(FakeRouter):
    async def matrix(self, sources, targets, mode):
        raise RoutingUnavailable("down")

    async def route(self, a, b, mode):
        raise RoutingUnavailable("down")


async def test_router_down_falls_back_to_estimates_and_flags_it():
    w = World()
    plan = await plan_days(
        [SAT], "normal", [], w.pick("Музей Кастеева", "Собор", "Галерея"),
        w.pick("Чайхана", "Бистро"),
        w.hours, RouterMatrix(DownRouter()), DirectionsLegs(DownRouter(), None, TARIFFS),
    )  # fmt: skip
    assert plan.travel_estimated
    assert any(x.code == "travel_estimated" for x in plan.warnings)
    day = plan.days[0]
    assert len(day.stops) >= 4
    assert all(leg.estimated and leg.default_mode is None for leg in day.legs)


async def test_explicit_start_point_adds_a_first_leg():
    w = World()
    start = (43.2200, 76.9200)
    plan = await run(w, [SAT], "normal", [], w.pick("Музей Кастеева", "Собор"),
                     w.pick("Чайхана", "Бистро"), start_point=start)  # fmt: skip
    day = plan.days[0]
    assert not plan.start_point_default and len(day.legs) == len(day.stops)
    assert day.legs[0].origin_place_id is None


async def test_hours_missing_is_assumed_and_flagged():
    w = World()
    plan = await run(
        w, [SAT], "normal", [], w.pick("Парк Горького", "Монумент"), w.pick("Чайхана", "Бистро")
    )
    assert any(x.code == "hours_assumed" for x in plan.warnings)
    assert all(
        s.hours_assumed for s in plan.days[0].stops if s.place.name in {"Парк Горького", "Монумент"}
    )


# --- database (Ш-33 -> Ш-34) and real Valhalla ----------------------------------------
async def test_layout_from_database_selection(conn):
    await load_categories(conn)
    rows = [
        ("Музей Кастеева", 76.9535, 43.2570, "museum", 70),
        ("Парк Горького", 76.9565, 43.2540, "park", 75),
        ("Кок-Тобе", 76.9747, 43.2330, "viewpoint", 80),
        ("Монумент", 76.9450, 43.2380, "monument", 60),
        ("Чайхана", 76.9300, 43.2400, "cafe_oriental", 60),
        ("Дастархан", 76.9310, 43.2410, "cafe_kazakh", 50),
        ("Бистро", 76.9450, 43.2500, "cafe_european", 40),
    ]
    ids = {}
    for name, lon, lat, cat, pop in rows:
        ids[name] = await add_place(conn, name, lon, lat, cat, "active", pop)
    # museum closed on Mondays, park round the clock-ish; the rest without hours
    for wd in range(1, 7):
        await conn.execute(
            "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES (%s, %s, %s, %s)",
            (ids["Музей Кастеева"], wd, time(10, 0), time(18, 0)),
        )
    brief = {
        "start_date": MON, "end_date": MON + timedelta(days=1), "budget_kzt": 100000,
        "has_accommodation": True, "must_haves": ["Музей Кастеева"], "interests": [],
        "pace": "normal", "crowd_tolerance": None,
    }  # fmt: skip
    sel = await select_candidates(conn, brief)
    hours = await hrs.load_hours(
        conn, [p.id for p in sel.must_have_places] + [c.place.id for c in sel.activities + sel.food]
    )
    assert len(hours[ids["Музей Кастеева"]]) == 6
    plan = await layout.layout_selection(conn, sel, brief, HaversineMatrix(), legs_provider())
    check_invariants(plan, hours, "normal")
    museum_day = next(
        d for d in plan.days if ids["Музей Кастеева"] in {s.place.id for s in d.stops}
    )
    assert museum_day.date == MON + timedelta(days=1)  # Monday it is closed


@needs_valhalla
async def test_real_valhalla_day():
    from app.routing import ValhallaRouter

    w = World()
    router = ValhallaRouter(VALHALLA)
    try:
        plan = await plan_days(
            dates(SAT, 2), "normal", w.pick("Медеу"),
            w.pick("Музей Кастеева", "Парк Горького", "Кок-Тобе", "Монумент", "Галерея", "Собор"),
            w.pick("Чайхана", "Дастархан", "Бистро", "Хинкальная"), w.hours,
            RouterMatrix(router), DirectionsLegs(router, None, TARIFFS), UnknownForecast(),
        )  # fmt: skip
    finally:
        await router.aclose()
    check_invariants(plan, w.hours, "normal")
    assert not plan.must_have_unplaced
    assert not plan.travel_estimated or any(x.code == "travel_estimated" for x in plan.warnings)


# --- Ш-36: must-have retry and determinism ------------------------------------------------
MORNING = [(wd, time(10, 0), time(12, 0)) for wd in range(7)]  # one 90-minute visit fits


def two_clashing_must_haves():
    """Two must-haves at one spot, both open only 10-12: the first pass puts both on one day."""
    a = mk("Музей А", 43.2570, 76.9535, "museum", "culture", visit=90)
    b = mk("Музей Б", 43.2570, 76.9535, "museum", "culture", visit=90)
    return a, b, {a.id: MORNING, b.id: MORNING}


async def test_must_have_that_does_not_fit_its_day_is_tried_on_other_days(monkeypatch):
    w = World()
    a, b, hours = two_clashing_must_haves()
    days2 = dates(SAT, 2)
    food = w.pick("Чайхана", "Дастархан", "Бистро", "Хинкальная")
    hours.update({p.id: w.hours[p.id] for p in food})

    monkeypatch.setattr(layout, "MUST_HAVE_RETRIES", 0)  # the Ш-34 behaviour
    before = await run(w, days2, "normal", [a, b], [], food, hours=hours)
    assert [u.reason for u in before.must_have_unplaced] == ["no_time"]

    monkeypatch.setattr(layout, "MUST_HAVE_RETRIES", 3)
    plan = await run(w, days2, "normal", [a, b], [], food, hours=hours)
    assert not plan.must_have_unplaced
    where = {s.place.name: d.date for d in plan.days for s in d.stops}
    assert where["Музей А"] != where["Музей Б"]
    check_invariants(plan, hours, "normal")


async def test_must_have_stays_reported_when_no_day_can_take_it():
    w = World()
    a, b, hours = two_clashing_must_haves()
    c = mk("Музей В", 43.2570, 76.9535, "museum", "culture", visit=90)
    hours[c.id] = MORNING  # three clashing visits, two days: one cannot fit anywhere
    food = w.pick("Чайхана", "Дастархан", "Бистро", "Хинкальная")
    hours.update({p.id: w.hours[p.id] for p in food})
    plan = await run(w, dates(SAT, 2), "normal", [a, b, c], [], food, hours=hours)
    assert len(plan.must_have_unplaced) == 1  # honest, not silent
    assert plan.must_have_unplaced[0].reason == "no_time"


def fingerprint(plan):
    return [
        (
            day.date,
            [(s.place.id, s.kind, s.meal, s.start, s.end) for s in day.stops],
            [(g.origin_place_id, g.destination_place_id, g.default_mode, g.travel_s)
             for g in day.legs],
        )
        for day in plan.days
    ] + [
        sorted((u.place.id, u.reason, u.date) for u in plan.unplaced),
        [(x.code, x.date, x.detail) for x in plan.warnings],
    ]  # fmt: skip


async def test_the_same_input_gives_an_identical_plan():
    w = World()
    days5 = dates(MON, 5)
    args = dict(
        dts=days5, pace="dense", must=w.pick("Музей закрыт по понедельникам", "Медеу", "Шанхай"),
        acts=w.pick(
            "Парк Горького", "Кок-Тобе", "Монумент", "Галерея", "Собор", "Зелёный базар", "Театр",
            "Музей Кастеева", "Музей инструментов", "Ботанический сад", "ТРЦ Мега", "Бутаковка",
        ),
        food=w.pick("Дастархан", "Хинкальная", "Бистро", "Чайхана", "Ужин у Медеу"),
        forecast=Rain({days5[1], days5[3]}),
    )  # fmt: skip
    plans = [fingerprint(await run(w, **args)) for _ in range(3)]
    assert plans[0] == plans[1] == plans[2]
    assert any(day[1] for day in plans[0][:5])  # not an empty plan
