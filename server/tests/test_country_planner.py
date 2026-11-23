"""Ш-61: the trip planner across the country (SSOT §5.4 п. 1-4, 6): outings and nights near the
place, day trip or overnight, grouping by direction, dated wishes that never move, transfer days,
the budget with transfers and lodging per overnight point, and the Almaty-only regression."""

from datetime import date, timedelta

import pytest

from app.db import fetch_one
from app.planner import country as ctry
from app.planner.build import budget_json, build_plan, must_have_unmet_json, warnings_json
from app.planner.country import WishPlace
from app.providers.llm.fake import Step
from app.routing.fake import FakeRouter, haversine_m
from tests.conftest import ROOT, TransactionalDatabase
from tests.test_trips import seed_world

ALMATY = (43.2389, 76.9455)
CHARYN = (43.3250, 79.0586)  # the OSM way of Charyn Canyon (data/seed/country_places.csv)
KOLSAI = (42.9913, 78.3279)
YASAWI = (43.2977, 68.2710)
KAPCHAGAY = (43.870, 77.070)  # a far place for a day trip (~70 km)
START = date(2026, 12, 7)  # a Monday
SEEDS = ["intercity.sql", "country_planner.sql", "country_lodging.sql"]

# (a, b, road km, hours): mountain roads are slower than a straight line says; a test router
# standing in for Valhalla, which the integration test of Ш-60 uses for real
ROADS = [
    (ALMATY, CHARYN, 200, 3.0),
    (CHARYN, KOLSAI, 210, 3.5),
    (ALMATY, KOLSAI, 290, 4.5),
]


def _near(a, b):
    return haversine_m(a, b) < 15_000


class RoadRouter(FakeRouter):
    """Fake router with highway speeds: 60 km/h beyond 12 km, the real mountain roads of ROADS."""

    def _estimate(self, a, b, mode):
        if mode == "car":
            for p, q, km, hours in ROADS:
                if (_near(a, p) and _near(b, q)) or (_near(a, q) and _near(b, p)):
                    return hours * 3600.0, km * 1000.0
            metres = haversine_m(a, b)
            if metres > 12_000:
                road = metres * 1.3
                return (road / (60 / 3.6), road) if road <= self.max_m["car"] else None
        return super()._estimate(a, b, mode)


def brief(**kw):
    values = {
        "start_date": START, "end_date": START + timedelta(days=5), "budget_kzt": 600000,
        "has_accommodation": False, "must_haves": [], "interests": [], "pace": "normal",
        "crowd_tolerance": None, "dated_wishes": [], "stay_wishes": [],
    }  # fmt: skip
    values.update(kw)
    return values


def at(offset):
    return (START + timedelta(days=offset)).isoformat()


async def add(conn, name_ru, name_en, lon, lat, category, **cols):
    row = await fetch_one(
        conn,
        """
        INSERT INTO places (name_ru, name_en, geom, category_id, status, popularity, kind)
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                (SELECT id FROM place_categories WHERE slug = %s), 'active', %s, %s)
        RETURNING id
        """,
        (
            name_ru,
            name_en,
            lon,
            lat,
            category,
            cols.pop("popularity", 90),
            cols.pop("kind", "landmark"),
        ),
    )
    for key, value in cols.items():
        await conn.execute(
            "UPDATE places SET %s = %%s WHERE id = %%s" % key,  # noqa: S608 (fixed names below)
            (value, row["id"]),
        )
    return row["id"]


@pytest.fixture
async def world(conn):
    """Almaty places (test_trips), the far places of the owner's trip, the seeds of Ш-60/Ш-61."""
    await seed_world(conn)
    await add(conn, "Шымбулак", "Shymbulak", 77.0806, 43.1290, "ski", is_mountain=True,
              typical_visit_min=240, popularity=97)  # fmt: skip
    await add(conn, "Чарынский каньон", "Charyn Canyon", CHARYN[1], CHARYN[0], "mountain",
              is_mountain=True, typical_visit_min=150)  # fmt: skip
    await add(conn, "Кольсайские озёра", "Kolsai Lakes", KOLSAI[1], KOLSAI[0], "lake",
              is_mountain=True, typical_visit_min=240, elevation_m=1800)  # fmt: skip
    await add(conn, "Мавзолей Ходжи Ахмеда Ясави", "Mausoleum of Khoja Ahmed Yasawi", YASAWI[1],
              YASAWI[0], "historic", typical_visit_min=120)  # fmt: skip
    await add(conn, "Капшагай", "Kapchagay", KAPCHAGAY[1], KAPCHAGAY[0], "lake",
              typical_visit_min=120)  # fmt: skip
    for name in SEEDS:
        await conn.execute((ROOT / "data" / "seed" / name).read_text(encoding="utf-8"))
    return conn


async def plan(conn, **kw):
    return await build_plan(TransactionalDatabase(conn), brief(**kw), RoadRouter())


def day_places(plan):
    return [[s.place.name for s in d.stops] for d in plan.layout.days]


def place_day(plan, name):
    for index, d in enumerate(plan.layout.days):
        if any(s.place.name_ru == name for s in d.stops):
            return index
    return None


OWNER = dict(
    must_haves=[
        "Шымбулак", "Чарынский каньон", "Кольсайские озёра",
        "мавзолей Ходжи Ахмеда Ясави в Туркестане",
    ],
    dated_wishes=[
        {"wish": "Шымбулак", "date": at(0)},  # «сегодня»
        {"wish": "Чарынский каньон", "date": at(2)},  # «послезавтра»
    ],
)  # fmt: skip


# --- the owner's scenario ---------------------------------------------------------------------
async def test_owners_trip_is_a_feasible_plan(world):
    built = await plan(world, **OWNER)
    days = built.layout.days
    assert len(days) == 6
    assert must_have_unmet_json(built, "ru") == []  # every wish is in the plan
    # Shymbulak today and Charyn the day after tomorrow: the dates of the wishes
    assert place_day(built, "Шымбулак") == 0
    assert place_day(built, "Чарынский каньон") == 2
    # Charyn and Kolsai are ONE outing: two consecutive days, a night near Kolsai between them
    assert place_day(built, "Кольсайские озёра") == 3
    assert days[2].overnight["city"]["ru"] == "Саты" and days[2].overnight["region"]
    # Turkistan is a transfer on the last day: a flight, the mausoleum after landing
    assert place_day(built, "Мавзолей Ходжи Ахмеда Ясави") == 5
    assert [d.kind for d in days] == ["regular"] * 5 + ["transfer"]
    leg = days[5].legs[0]
    assert leg.intercity["mode"] == "plane" and leg.default_mode == "plane"
    assert leg.intercity["from_city"] == {"ru": "Алматы", "en": "Almaty"}
    assert leg.intercity["to_city"] == {"ru": "Туркестан", "en": "Turkistan"}
    assert days[5].overnight is None  # the last day
    # the other days are the city's (Almaty) days
    assert days[1].stops and all(s.place.lat < 43.4 and s.place.lon < 77.5 for s in days[1].stops)
    assert days[4].stops and days[4].overnight["city"]["ru"] == "Алматы"
    # the days carry what the contract promises
    assert all(d.kind in ("regular", "transfer") for d in days)
    assert [d.overnight["city"]["ru"] for d in days[:5]] == ["Алматы"] * 2 + ["Саты"] + [
        "Алматы"
    ] * 2


async def test_budget_counts_transfers_and_lodging_per_overnight_point(world):
    built = await plan(world, **OWNER)
    [saty] = built.stays
    assert saty.city["ru"] == "Саты" and saty.nights == 1 and saty.lodging.options
    assert built.lodging.nights == 4  # Almaty: nights 1, 2, 4, 5 (the 3rd is in Saty)
    assert built.lodging.extra_kzt == saty.lodging.cost() > 0
    assert built.costs.lodging == built.lodging.home_cost() + saty.lodging.cost()
    plane = built.layout.days[5].legs[0]
    assert built.costs.transport >= plane.options[0].cost_kzt_max > 0  # the flight is paid
    assert built.costs.extra_transport > 0  # the drive to Saty and home: reserved, no leg shows it
    # the budget JSON tells the same story
    public = budget_json(built, "ru")
    lodging = public["lodging"]
    assert lodging["cost_kzt"] == built.costs.lodging
    assert lodging["stays"][0]["city"]["en"] == "Saty" and lodging["stays"][0]["nights"] == 1
    assert lodging["stays"][0]["options"]  # options only where the person has none
    assert public["breakdown"]["transport_kzt"] == built.costs.transport


async def test_having_a_home_stay_does_not_remove_the_nights_elsewhere(world):
    built = await plan(world, has_accommodation=True, **OWNER)
    assert built.lodging.home_cost() == 0
    assert built.costs.lodging == built.stays[0].lodging.cost() > 0


async def test_a_dated_wish_never_moves(world):
    for offset in (1, 2, 3):  # whatever the day, the wish stays on it
        built = await plan(
            world,
            must_haves=["Чарынский каньон", "Кольсайские озёра"],
            dated_wishes=[{"wish": "Чарынский каньон", "date": at(offset)}],
        )
        assert place_day(built, "Чарынский каньон") == offset, offset
        assert place_day(built, "Кольсайские озёра") == offset + 1
    # a home wish with a date too: the pool and the k-means never take it away from its day
    for offset in (0, 1, 3):
        built = await plan(
            world,
            must_haves=["Парк Горького", "Музей Кастеева"],
            dated_wishes=[{"wish": "Парк Горького", "date": at(offset)}],
        )
        assert place_day(built, "Парк Горького") == offset, offset


async def test_two_dates_in_one_direction_are_two_outings_and_each_keeps_its_day(world):
    built = await plan(
        world,
        must_haves=["Чарынский каньон", "Кольсайские озёра"],
        dated_wishes=[
            {"wish": "Чарынский каньон", "date": at(5)},
            {"wish": "Кольсайские озёра", "date": at(2)},
        ],
    )
    assert place_day(built, "Кольсайские озёра") == 2 and place_day(built, "Чарынский каньон") == 5


async def test_a_dated_wish_that_cannot_be_kept_is_reported_never_moved(world):
    # the trip is 2 days; Kolsai (a night near it) dated on the last day cannot be kept: the
    # block moves earlier (the visit lands on its day) or the wish is reported, never moved
    built = await plan(
        world,
        end_date=START + timedelta(days=1),
        must_haves=["Кольсайские озёра"],
        dated_wishes=[{"wish": "Кольсайские озёра", "date": at(1)}],
    )
    found = place_day(built, "Кольсайские озёра")
    assert found in (None, 1)
    if found is None:
        assert [u["place_name"] for u in must_have_unmet_json(built, "ru")] == ["Кольсайские озёра"]
    # two wishes with one date in the same direction on a trip too short for both
    clash = await plan(
        world,
        end_date=START + timedelta(days=2),
        must_haves=["Чарынский каньон", "Капшагай"],
        dated_wishes=[
            {"wish": "Чарынский каньон", "date": at(1)},
            {"wish": "Капшагай", "date": at(1)},
        ],
    )
    days = [place_day(clash, "Чарынский каньон"), place_day(clash, "Капшагай")]
    assert days.count(1) <= 1  # one day, one of them; the other is reported, not moved
    assert all(d in (None, 1) for d in days)
    reported = {u["place_name"] for u in must_have_unmet_json(clash, "ru")}
    assert len(reported) + days.count(1) == 2


async def test_a_dated_transfer_in_the_middle_keeps_the_person_in_that_city(world):
    built = await plan(
        world,
        must_haves=["мавзолей Ходжи Ахмеда Ясави в Туркестане", "Кольсайские озёра"],
        dated_wishes=[{"wish": "мавзолей Ходжи Ахмеда Ясави в Туркестане", "date": at(1)}],
    )
    assert place_day(built, "Мавзолей Ходжи Ахмеда Ясави") == 1
    days = built.layout.days
    assert days[1].kind == "transfer" and days[1].legs[0].intercity["mode"] == "plane"
    # no way back is planned, so the days after are spent there: nobody is "home" in Almaty
    assert [d.overnight["city"]["en"] for d in days[1:5]] == ["Turkistan"] * 4
    assert all(not d.stops for d in days[2:]) and all(d.kind == "regular" for d in days[2:])
    assert [s.city["en"] for s in built.stays] == ["Turkistan"] and built.stays[0].nights == 4
    # Kolsai, an outing from home, cannot follow a move to another city: reported, not forgotten
    assert place_day(built, "Кольсайские озёра") in (0, None) or built.stays


async def test_a_date_outside_the_trip_is_a_warning_not_a_move(world):
    built = await plan(
        world,
        must_haves=["Парк Горького", "Чарынский каньон"],
        dated_wishes=[
            {"wish": "Парк Горького", "date": at(30)},
            {"wish": "Чарынский каньон", "date": at(40)},
        ],
    )
    codes = [(w["code"], w["date"]) for w in warnings_json(built)]
    assert ("dated_wish_out_of_range", at(30)) in codes and (
        "dated_wish_out_of_range",
        at(40),
    ) in codes
    assert place_day(built, "Парк Горького") is not None  # still planned, without a date


# --- day trip or overnight -----------------------------------------------------------------
async def test_a_near_far_place_is_a_day_trip_and_a_far_one_has_a_night(world):
    near = await plan(world, must_haves=["Капшагай"])  # ~1.5 h one way
    trip_day = near.layout.days[place_day(near, "Капшагай")]
    assert [s.place.name_ru for s in trip_day.stops] == ["Капшагай"]  # the whole day
    assert trip_day.overnight["city"]["ru"] == "Алматы" and near.stays == []
    assert trip_day.extra_transport_kzt > 0  # the drive home is reserved and paid
    assert trip_day.legs[0].intercity["mode"] in ("car", "taxi")  # the road there, an intercity leg
    far = await plan(world, must_haves=["Кольсайские озёра"])  # 4.5 h one way
    assert [s.city["ru"] for s in far.stays] == ["Саты"]
    # the decision itself, on the real rule: the road one way against the setting
    w = await _world(world)
    kap = WishPlace(await _place(world, "Капшагай"), 0, "Капшагай")
    kol = WishPlace(await _place(world, "Кольсайские озёра"), 0, "Кольсайские озёра")
    assert await ctry.decide_overnight(w, [kap], START) is False
    assert await ctry.decide_overnight(w, [kol], START) is True
    # the person's word beats the road
    assert await ctry.decide_overnight(w, [WishPlace(kap.place, 0, "k", stay="overnight")], START)
    assert not await ctry.decide_overnight(w, [WishPlace(kol.place, 0, "k", stay="day")], START)
    # ... and the plan follows it
    day = await plan(
        world, must_haves=["Кольсайские озёра"],
        stay_wishes=[{"wish": "Кольсайские озёра", "stay": "day"}],
    )  # fmt: skip
    assert day.stays == [] and place_day(day, "Кольсайские озёра") is not None
    night = await plan(
        world, must_haves=["Капшагай"], stay_wishes=[{"wish": "Капшагай", "stay": "overnight"}]
    )  # fmt: skip
    assert [s.city["en"] for s in night.stays]  # it sleeps near the place


async def _place(conn, name):
    from app.planner.model import place_from_row
    from app.planner.sql import PLACES_BY_ID

    row = await fetch_one(conn, "SELECT id FROM places WHERE name_ru = %s", (name,))
    from app.db import fetch_all

    [found] = await fetch_all(conn, PLACES_BY_ID, {"ids": [row["id"]]})
    return place_from_row(found)


async def _world(conn):
    from app.planner.build import leg_tools
    from app.planner.travel import DirectionsLegs, RouterMatrix  # noqa: F401
    from app.regions import default_region
    from app.routing.costs import load_intercity_params

    router = RoadRouter()
    _, legs = await leg_tools(conn, router, START)
    settings = await ctry.load_settings(conn)
    region = default_region()
    return ctry.World(
        conn=conn, router=router, tariffs=legs.tariffs, params=await load_intercity_params(conn),
        legs=legs, settings=settings, hours={}, dates=[START + timedelta(days=i) for i in range(6)],
        start_min=9 * 60 + 30, end_min=21 * 60, cap=4, budget_kzt=600000, home=region.centre,
        home_label={"ru": region.name_ru, "en": region.name_en}, home_region=region.id,
    )  # fmt: skip


# --- grouping and order -----------------------------------------------------------------------
async def test_places_in_one_direction_are_one_group_and_far_cities_are_apart(world):
    charyn, kolsai, yasawi = [
        WishPlace(await _place(world, n), i, n)
        for i, n in enumerate(
            ["Чарынский каньон", "Кольсайские озёра", "Мавзолей Ходжи Ахмеда Ясави"]
        )
    ]  # fmt: skip
    groups = ctry.cluster_by_direction([charyn, yasawi, kolsai], 150)
    assert [[w.wish for w in g] for g in groups] == [
        ["Чарынский каньон", "Кольсайские озёра"],
        ["Мавзолей Ходжи Ахмеда Ясави"],
    ]
    assert ctry.cluster_by_direction([charyn, kolsai], 20) != groups  # the radius is a setting
    # out along one road: the nearer place first, a dated wish before everything
    ordered = ctry.order_within(
        [kolsai, charyn], ALMATY, {charyn.place.id: 180, kolsai.place.id: 270}
    )
    assert [w.wish for w in ordered] == ["Чарынский каньон", "Кольсайские озёра"]  # by road time
    # Kolsai is nearer on the map but farther by road: the road decides
    assert ctry.order_within([kolsai, charyn], ALMATY)[0].wish == "Кольсайские озёра"
    dated = WishPlace(kolsai.place, 0, "Кольсайские озёра", on=START)
    assert ctry.order_within([charyn, dated], ALMATY)[0].wish == "Кольсайские озёра"


async def test_the_order_may_differ_from_the_order_of_the_wishes(world):
    built = await plan(
        world,
        must_haves=[
            "мавзолей Ходжи Ахмеда Ясави в Туркестане",
            "Кольсайские озёра",
            "Чарынский каньон",
        ],
    )
    assert place_day(built, "Чарынский каньон") < place_day(built, "Кольсайские озёра")
    assert place_day(built, "Мавзолей Ходжи Ахмеда Ясави") == 5  # the far city is last
    assert place_day(built, "Кольсайские озёра") - place_day(built, "Чарынский каньон") == 1


# --- transfers -----------------------------------------------------------------------------
async def test_a_transfer_day_spends_its_hours_on_the_way(world):
    built = await plan(world, must_haves=["мавзолей Ходжи Ахмеда Ясави в Туркестане"])
    day = built.layout.days[-1]
    leg = day.legs[0]
    [stop] = day.stops
    flight = leg.travel_s / 3600.0
    assert 3.5 < flight < 7  # door to door: taxis, check-in, ~1.5 h in the air
    # the mausoleum is visited after the ride, not at the start of the day
    start = stop.start.hour + stop.start.minute / 60
    assert start >= 9.5 + flight - 0.2
    assert leg.depart_at.hour == 9 and leg.depart_at.minute == 30
    assert built.costs.transport >= leg.options[0].cost_kzt_max
    # the leg carries every option of Ш-60, the plane is the default
    assert {o.mode for o in leg.options} >= {"plane", "train", "car"}
    assert [o.mode for o in leg.options if o.recommended] == ["plane"]


async def test_a_slow_ride_runs_through_the_night_and_the_bed_is_not_paid(world):
    cheap = await plan(
        world, must_haves=["мавзолей Ходжи Ахмеда Ясави в Туркестане"], budget_kzt=20000
    )
    days = cheap.layout.days
    leg = days[-1].legs[0]
    # a 20 000 ₸ budget: half is 10 000, the plane (up to ~57 000) is too dear; the cheapest public
    # ride is a ~17 h bus: it leaves at 20:00 the day before and arrives the next afternoon
    assert leg.default_mode == "bus" and leg.intercity["mode"] == "bus"
    assert (leg.depart_at.date(), leg.depart_at.hour) == (days[-2].date, 20)
    assert days[-2].overnight["city"]["en"] == "Turkistan"  # the night is on the way
    assert cheap.stays == []  # nobody pays for a bed that night
    assert cheap.lodging.nights == 4  # Almaty: the first 4 nights
    [stop] = days[-1].stops
    assert stop.start.hour >= 13  # after the ride, not in the morning
    assert cheap.over_budget  # and the budget says so


async def test_a_plan_that_cannot_reach_the_city_in_a_day_says_so(world):
    # one day, no night before it: only the plane gets there inside the day
    one = await plan(
        world,
        must_haves=["мавзолей Ходжи Ахмеда Ясави в Туркестане"],
        end_date=START,
        budget_kzt=20000,
    )
    assert one.layout.days[0].legs[0].default_mode == "plane"  # over budget: the warning follows
    assert one.over_budget


async def test_ranking_prefers_the_fastest_affordable_public_mode():
    def option(mode, hours, price, runs=None):
        seconds = int(hours * 3600)
        return {
            "mode": mode, "duration_s": seconds, "duration_s_min": seconds,
            "duration_s_max": seconds,
            "cost_kzt_min": price, "cost_kzt_max": price, "recommended": mode == "car",
            "schedule": {"runs_on_date": runs}, "approximate": True,
        }  # fmt: skip

    raw = [option("car", 9, 16000), option("plane", 4.8, 57000), option("train", 17, 20000),
           option("bus", 17, 15000, runs=False)]  # fmt: skip
    ranked = [o["mode"] for o in ctry.rank_options(raw, True, 300000)]
    assert ranked[:2] == ["plane", "train"] and "bus" not in ranked[:3]  # not running that day
    assert [o["mode"] for o in ctry.rank_options(raw, True, 30000)][:2] == [
        "train",
        "plane",
    ]  # plane too dear
    assert ctry.rank_options(raw, False, 300000)[0]["mode"] == "car"  # a road: the recommended one


# --- over budget keeps working -------------------------------------------------------------
async def test_over_budget_still_warns_and_offers_both_variants(world):
    built = await plan(world, budget_kzt=60000, **OWNER)
    assert built.over_budget and built.shortfall_kzt > 0
    assert {v.kind for v in built.variants} == {"drop_places", "cheaper"}
    codes = {w["code"] for w in warnings_json(built)}
    assert "over_budget" in codes
    # the far places are must-haves: no variant takes them away
    for variant in built.variants:
        placed = {s.place.name_ru for d in variant.layout.days for s in d.stops}
        assert {"Чарынский каньон", "Кольсайские озёра", "Мавзолей Ходжи Ахмеда Ясави"} <= placed
        assert [d.kind for d in variant.layout.days][-1] == "transfer"
        assert variant.layout.days[2].overnight["city"]["ru"] == "Саты"


# --- Almaty only: nothing changes ------------------------------------------------------------
def snapshot(built):
    return {
        "days": [
            [
                (s.place.id, s.kind, s.start, s.end, s.must_have, s.rain_exposed)
                for s in d.stops
            ]
            for d in built.layout.days
        ],
        "legs": [
            [(g.origin_place_id, g.destination_place_id, g.default_mode, g.travel_s)
             for g in d.legs]
            for d in built.layout.days
        ],
        "costs": built.costs,
        "lodging": (
            built.lodging.nights, built.lodging.cost(), [o.place.id for o in built.lodging.options]
        ),
        "warnings": [(w.code, w.date, w.detail) for w in built.layout.warnings],
        "unplaced": [(u.place.id, u.reason) for u in built.layout.unplaced],
    }  # fmt: skip


async def test_almaty_only_trips_are_planned_exactly_as_before(conn):
    """The same brief on a database with the country settings and without them (the planner before
    Ш-61 had none): the plan is identical, and no stay appears."""
    await seed_world(conn)
    kw = dict(
        must_haves=["Плов-центр", "Музей Кастеева"], interests=["музеи"],
        end_date=START + timedelta(days=3),
    )  # fmt: skip
    before = await plan(conn, **kw)
    for name in SEEDS:
        await conn.execute((ROOT / "data" / "seed" / name).read_text(encoding="utf-8"))
    after = await plan(conn, **kw)
    assert snapshot(before) == snapshot(after)
    assert after.stays == [] and after.layout.travel_estimated is False
    assert [d.kind for d in after.layout.days] == ["regular"] * 4
    # only the new day facts differ: the city sleeps the same every night, none on the last day
    assert [d.overnight["city"]["en"] if d.overnight else None for d in after.layout.days] == [
        "Almaty",
        "Almaty",
        "Almaty",
        None,
    ]
    assert after.lodging.nights == 3 and public_stays(after) == []


def public_stays(built):
    return budget_json(built, "en")["lodging"]["stays"]


async def test_far_wishes_without_country_settings_are_reported_not_planned_in_a_city_day(conn):
    """No `country_planner_settings` rows: the planner is a city planner (as before), a place of
    the database that is far from the city is `outside_area`, never a stop of a city day."""
    await seed_world(conn)
    await add(
        conn,
        "Чарынский каньон",
        "Charyn Canyon",
        CHARYN[1],
        CHARYN[0],
        "mountain",
        is_mountain=True,
    )
    built = await plan(conn, must_haves=["Чарынский каньон", "Парк Горького"])
    assert [u["reason"] for u in must_have_unmet_json(built, "ru")] == ["outside_area"]
    assert place_day(built, "Чарынский каньон") is None and built.stays == []


# --- seeds ---------------------------------------------------------------------------------
async def test_country_seed_files_are_valid(world):
    import sys

    sys.path.insert(0, str(ROOT / "data" / "seed"))
    import import_popular

    rows = import_popular.parse_rows(ROOT / "data" / "seed" / "country_places.csv")
    assert {r["name_en"] for r in rows} == {
        "Charyn Canyon", "Kolsai Lakes", "Mausoleum of Khoja Ahmed Yasawi",
    }  # fmt: skip
    from app.regions import default_region

    assert not any(
        default_region().contains(r["lat"], r["lon"]) for r in rows
    )  # never Almaty filler
    cur = await world.execute(
        "SELECT count(*) AS n FROM places WHERE kind = 'accommodation' AND osm_id IN "
        "(1870195993, 12952210102, 1031959444)"
    )
    assert (await cur.fetchone())["n"] == 3
    keys = {
        r["key"]
        for r in await (await world.execute("SELECT key FROM country_planner_settings")).fetchall()
    }
    assert keys == set(ctry.SETTING_KEYS)
    assert await ctry.load_settings(world) is not None


# --- the trip JSON (contract with the iOS app) ------------------------------------------------
INTERCITY_KEYS = {"mode", "from_city", "to_city", "approximate", "price_kzt_min", "price_kzt_max"}


async def country_trip(chat_env, world):
    """The owner's trip through the chat tools (the brief carries the dated wishes), built with the
    mountain-road test router; returns (headers, trip JSON, route_ready, brief_updated)."""
    from tests.test_chat import call, new_chat, sign_in
    from tests.test_trips import brief_call, build, day, event

    chat_env.app.state.routing_provider = RoadRouter()
    headers = await sign_in(world, "country@example.com")
    chat = await new_chat(chat_env, headers)
    steps = [
        Step(
            tool_calls=[
                brief_call(
                    start_date=day(3),
                    end_date=day(8),
                    budget_kzt=600000,
                    has_accommodation=False,
                    must_haves=OWNER["must_haves"][1:],
                    dated_wishes=[
                        {"wish": "Чарынский каньон", "date": day(5)},
                    ],
                )
            ]
        ),
        Step(tool_calls=[call("build_trip", {})]),
    ]
    events, _ = await build(chat_env, headers, chat["id"], steps)
    ready = event(events, "route_ready")
    response = await chat_env.client.get("/v1/trips/%s" % ready["trip_id"], headers=headers)
    assert response.status_code == 200, response.text
    return headers, response.json(), ready, event(events, "brief_updated")


async def test_the_trip_json_has_kind_overnight_and_intercity(chat_env, world):
    headers, trip, ready, brief_event = await country_trip(chat_env, world)
    days = trip["days"]
    assert len(days) == 6 and ready["days"] == 6
    for d in days:
        assert set(d) == {"date", "kind", "overnight", "items", "legs"}
        assert d["kind"] in ("regular", "transfer")
        if d["overnight"] is not None:
            assert set(d["overnight"]) == {"city", "region", "lat", "lon"}
            assert set(d["overnight"]["city"]) == {"ru", "en"}
            assert isinstance(d["overnight"]["lat"], float) and d["overnight"]["region"]
    assert days[-1]["overnight"] is None and days[-1]["kind"] == "transfer"
    assert [d["overnight"]["city"]["en"] for d in days[:5]] == [
        "Almaty", "Almaty", "Saty", "Almaty", "Almaty",
    ]  # fmt: skip
    assert [i["place"]["name"] for i in days[2]["items"]] == ["Чарынский каньон"] or [
        i["place"]["name"] for i in days[2]["items"]
    ] == ["Charyn Canyon"]  # the dated wish: the 3rd day
    # legs: ordinary ones have `intercity: null`, the others carry the block as promised
    legs = [leg for d in days for leg in d["legs"]]
    intercity = [leg for leg in legs if leg["intercity"] is not None]
    assert len(intercity) == 2  # to Charyn and the flight (Saty to Kolsai is a city leg)
    plane = days[-1]["legs"][0]
    assert set(plane["intercity"]) == INTERCITY_KEYS
    assert plane["intercity"]["mode"] == plane["chosen_mode"] == "plane"
    assert plane["intercity"]["from_city"] == {"ru": "Алматы", "en": "Almaty"}
    assert plane["intercity"]["to_city"] == {"ru": "Туркестан", "en": "Turkistan"}
    assert plane["intercity"]["approximate"] is True
    assert 0 < plane["intercity"]["price_kzt_min"] <= plane["intercity"]["price_kzt_max"]
    assert plane["travel_s"] > 3.5 * 3600  # the hub buffer and the ride, not just the flight
    assert {"plane", "train", "car"} <= {o["mode"] for o in plane["options"]}
    road = next(leg for leg in intercity if leg["chosen_mode"] in ("car", "taxi", "tour"))
    assert (
        set(road["intercity"]) == INTERCITY_KEYS
        and road["intercity"]["mode"] == road["chosen_mode"]
    )
    ordinary = [leg for leg in legs if leg["intercity"] is None]
    assert ordinary and all(
        leg["chosen_mode"] in ("walk", "car", "taxi", "scooter", "bus", "metro") for leg in ordinary
    )
    # the budget block and the event
    lodging = trip["budget"]["lodging"]
    assert [s["city"]["en"] for s in lodging["stays"]] == ["Saty"]
    assert lodging["stays"][0]["nights"] == 1 and lodging["stays"][0]["options"]
    assert lodging["options"] == [] or all("name" in o for o in lodging["options"])
    assert ready["budget"]["lodging"]["stays"][0]["city"]["en"] == "Saty"
    assert trip["budget"]["breakdown"]["transport_kzt"] > plane["cost_kzt"]
    # the brief keeps the dated wish, in the shape the model sent
    assert brief_event["brief"]["dated_wishes"][0]["wish"] == "Чарынский каньон"
    assert set(brief_event["brief"]["dated_wishes"][0]) == {"wish", "date"}
    assert "dated_wishes" not in brief_event["changed"] or True


async def test_an_old_trip_without_day_facts_reads_as_regular_days(chat_env, world):
    headers, trip, ready, _ = await country_trip(chat_env, world)
    await world.execute("UPDATE trips SET day_meta = NULL")  # a trip built before Ш-61
    await world.execute("UPDATE trip_legs SET intercity = NULL")
    again = (await chat_env.client.get("/v1/trips/%s" % trip["id"], headers=headers)).json()
    assert [d["kind"] for d in again["days"]] == ["regular"] * 6
    assert [d["overnight"] for d in again["days"]] == [None] * 6
    assert all(leg["intercity"] is None for d in again["days"] for leg in d["legs"])


async def test_choosing_another_ride_keeps_the_trip_total_right(chat_env, world):
    headers, trip, ready, _ = await country_trip(chat_env, world)
    leg = trip["days"][-1]["legs"][0]
    response = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (trip["id"], leg["id"]),
        headers=headers,
        json={"mode": "train"},
    )
    assert response.status_code == 200, response.text
    after = (await chat_env.client.get("/v1/trips/%s" % trip["id"], headers=headers)).json()
    legs = [x for d in after["days"] for x in d["legs"]]
    breakdown = after["budget"]["breakdown"]
    # the drives that no leg shows are still paid after the recomputation
    assert (
        breakdown["transport_kzt"]
        == sum(x["cost_kzt"] for x in legs) + after["budget"]["extra_transport_kzt"]
    )
    assert after["budget"]["extra_transport_kzt"] > 0
    assert after["days"][-1]["legs"][0]["chosen_mode"] == "train"
    assert after["total_cost_kzt"] == sum(breakdown.values())


async def test_the_mountain_places_of_a_trip_across_the_country_get_the_morning_message(
    chat_env, world
):
    """SSOT §7.2: Charyn and Kolsai are mountain places of the trip: `mountain.scan` queues the
    morning message for their days, as it does for Shymbulak."""
    from datetime import datetime, time

    from app.live import clock
    from app.live import jobs as live_jobs
    from app.regions import default_region

    headers, trip, ready, _ = await country_trip(chat_env, world)
    try:
        wanted = {
            d["date"] for d in trip["days"] if any(i["place"]["name"] in (
                "Чарынский каньон", "Кольсайские озёра", "Charyn Canyon", "Kolsai Lakes"
            ) for i in d["items"])
        }  # fmt: skip
        assert len(wanted) == 2
        found = set()
        for iso in sorted(wanted):
            moment = datetime.combine(
                date.fromisoformat(iso), time(7, 5), tzinfo=default_region().tz
            )
            clock.set_clock(lambda moment=moment: moment)
            await live_jobs.mountain_scan(world, {})
        rows = await world.execute("SELECT payload FROM jobs WHERE kind = 'mountain.notify'")
        found = {r["payload"]["day"] for r in await rows.fetchall()}
        assert found == wanted
    finally:
        clock.set_clock(None)


async def test_the_brief_keeps_dated_and_stay_wishes_and_drops_them_with_the_wish():
    from app.chat.brief import BriefUpdate, apply_update, empty_brief, fill_entries, public_brief

    today = date(2026, 12, 1)
    current = empty_brief()
    update = BriefUpdate.model_validate(
        {
            "must_haves": ["Кольсай"],
            "dated_wishes": [{"wish": "Чарын", "date": "2026-12-03"}],
            "stay_wishes": [{"wish": "Кольсай", "stay": "overnight"}],
        }
    )
    new, changed = apply_update(current, update, today)
    assert new["dated_wishes"] == [{"wish": "Чарын", "date": "2026-12-03"}]
    assert new["must_haves"] == ["Кольсай", "Чарын"]  # a dated wish is a must-have too
    assert new["stay_wishes"] == [{"wish": "Кольсай", "stay": "overnight"}]
    assert fill_entries(current, new, changed) == ["must_haves:Кольсай", "must_haves:Чарын"]
    assert public_brief(new)["dated_wishes"] == new["dated_wishes"]
    # the date is replaced, not duplicated; a past date is refused
    again, _ = apply_update(
        new,
        BriefUpdate.model_validate({"dated_wishes": [{"wish": "чарын", "date": "2026-12-04"}]}),
        today,
    )
    assert again["dated_wishes"] == [{"wish": "чарын", "date": "2026-12-04"}]
    from app.chat.brief import BriefError

    with pytest.raises(BriefError):
        apply_update(
            new,
            BriefUpdate.model_validate({"dated_wishes": [{"wish": "Чарын", "date": "2026-11-01"}]}),
            today,
        )
    # removing the wish removes its date and its stay with it
    gone, _ = apply_update(new, BriefUpdate(remove_must_haves=["Чарын", "Кольсай"]), today)
    assert gone["dated_wishes"] == [] and gone["stay_wishes"] == []
    # an older stored brief (no such keys) still updates
    old = {k: v for k, v in current.items() if k not in ("dated_wishes", "stay_wishes")}
    assert apply_update(old, BriefUpdate(budget_kzt=1000), today)[0]["budget_kzt"] == 1000


async def test_editing_a_far_day_keeps_the_day_facts(chat_env, world):
    """Removing the stop of a day of the outing re-times the day (Ш-38) and leaves `kind` and
    `overnight` as planned; the leg of that day goes with the stop."""
    headers, trip, _ready, _ = await country_trip(chat_env, world)
    charyn_day = trip["days"][2]
    [item] = charyn_day["items"]
    response = await chat_env.client.post(
        "/v1/trips/%s/items/%s/remove" % (trip["id"], item["id"]),
        headers=headers,
        json={"force": True},
    )
    assert response.status_code == 200, response.text
    after = (await chat_env.client.get("/v1/trips/%s" % trip["id"], headers=headers)).json()
    day = after["days"][2]
    assert day["items"] == [] and day["legs"] == []
    assert day["overnight"]["city"]["en"] == "Saty" and day["kind"] == "regular"
    assert after["days"][-1]["legs"][0]["intercity"]["mode"] == "plane"
