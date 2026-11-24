"""Ш-62: the chat and the live route across the country (SSOT §5.4 п. 2, 7; §11.1).

The owner's scenario on the scripted model: Shymbulak today, Charyn the day after tomorrow, the
Kolsai Lakes, the Yasawi mausoleum in Turkistan, "with a night", then the trip is built. The live
route carries intercity legs (the contract of the iOS app), the built trip puts Charyn on its day,
sleeps in Saty and makes Turkistan a transfer day. Plus: edits keep intercity legs, the offline
copy carries the day facts, the prompt v8 rules, and places Jol has no data for stay honest."""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.chat import api as chat_api
from app.chat import live_route, prompts
from app.chat.brief import today_in_region
from app.db import fetch_one
from app.planner import country as ctry
from app.providers.llm.fake import Step
from tests.conftest import parse_sse
from tests.test_chat import call, new_chat, say, sign_in, use
from tests.test_country_planner import YASAWI, RoadRouter, add, world  # noqa: F401 (fixture)
from tests.test_trips import event

CONTRACT = {"mode", "duration_s", "distance_m", "intercity"}
PRICES = {"price_kzt_min", "price_kzt_max"}
LIVE_MODES = {"plane", "train", "bus_intercity", "car", "tour"}


def day(offset):
    return (today_in_region() + timedelta(days=offset)).isoformat()


async def turn(env, headers, chat_id, *steps, text="hi"):
    """One chat turn; waits for the background live-route pass; returns (events, llm)."""
    llm = use(env, steps=list(steps) + [Step(text=["ok"])])
    response = await say(env, headers, chat_id, text)
    assert response.status_code == 200, response.text
    await chat_api.scheduler_of(env.app).drain()
    return parse_sse(response.text), llm


def brief_step(**fields):
    return Step(tool_calls=[call("update_trip_brief", fields)])


async def live(env, headers, chat_id):
    detail = await env.client.get("/v1/chats/%s" % chat_id, headers=headers)
    return detail.json()["live_route"]


def has_key(value, key):
    if isinstance(value, dict):
        return key in value or any(has_key(v, key) for v in value.values())
    return isinstance(value, list) and any(has_key(v, key) for v in value)


def tool_results(llm):
    """Every tool result the model saw, parsed."""
    out = []
    for c in llm.calls:
        for message in c.messages:
            if message.role == "tool":
                try:
                    out.append(json.loads(message.content))
                except ValueError:
                    pass
    return out


@pytest.fixture
async def owner(chat_env, world):  # noqa: F811
    chat_env.app.state.routing_provider = RoadRouter()
    headers = await sign_in(world, "owner62@example.com")
    chat = await new_chat(chat_env, headers)
    return SimpleNamespace(env=chat_env, conn=world, headers=headers, chat=chat, id=chat["id"])


async def run_scenario(o):
    """The five messages of the owner, then «собери поездку»; returns the per-turn results."""
    seen = {}
    seen["t1"] = await turn(
        o.env, o.headers, o.id,
        brief_step(
            start_date=day(0), end_date=day(5), budget_kzt=600000, has_accommodation=False,
            must_haves=["Шымбулак"], dated_wishes=[{"wish": "Шымбулак", "date": day(0)}],
        ),
        text="Хочу на Шымбулак сегодня",
    )  # fmt: skip
    seen["t2"] = await turn(
        o.env, o.headers, o.id,
        brief_step(
            must_haves=["Чарынский каньон"],
            dated_wishes=[{"wish": "Чарынский каньон", "date": day(2)}],
        ),
        text="послезавтра Чарын",
    )  # fmt: skip
    seen["t3"] = await turn(
        o.env, o.headers, o.id,
        brief_step(must_haves=["Кольсайские озёра"]),
        Step(text=["На день или с ночёвкой рядом?"]),
        text="Кольсайские озёра",
    )  # fmt: skip
    seen["t4"] = await turn(
        o.env, o.headers, o.id,
        brief_step(must_haves=["мавзолей Ходжи Ахмеда Ясави"]),
        text="и в Туркестан к мавзолею Ходжи Ахмеда Ясави",
    )  # fmt: skip
    seen["t5"] = await turn(  # the answer to «на день или с ночёвкой?»
        o.env, o.headers, o.id,
        brief_step(stay_wishes=[{"wish": "Кольсайские озёра", "stay": "overnight"}]),
        text="с ночёвкой",
    )  # fmt: skip
    seen["t6"] = await turn(
        o.env, o.headers, o.id, Step(tool_calls=[call("build_trip", {})]), text="собери поездку"
    )
    return seen


# --- the owner's scenario end to end ----------------------------------------------------------
async def test_owners_scenario_in_the_chat(owner):
    seen = await run_scenario(owner)

    # the live route: four stops, three legs, the far ones are intercity legs of the contract
    route = await live(owner.env, owner.headers, owner.id)
    assert [s["wish"] for s in route["stops"]] == [
        "Шымбулак", "Чарынский каньон", "Кольсайские озёра", "мавзолей Ходжи Ахмеда Ясави",
    ]  # fmt: skip
    legs = route["legs"]
    assert [(x["from_ord"], x["to_ord"]) for x in legs] == [(1, 2), (2, 3), (3, 4)]
    for leg in legs:
        assert CONTRACT <= set(leg) and set(leg) <= CONTRACT | PRICES | {"from_ord", "to_ord"}
        assert leg["intercity"] is True and leg["mode"] in LIVE_MODES
        assert leg["duration_s"] > 3000 and leg["distance_m"] > 50_000
    assert legs[0]["mode"] in ("car", "tour")  # ~190 km: an outing by road
    assert legs[1]["mode"] in ("car", "tour")  # Charyn -> Kolsai, one direction
    assert legs[2]["mode"] in ("plane", "train", "bus_intercity")  # a transfer between cities
    assert legs[2]["distance_m"] > 700_000  # Kolsai -> home -> Turkistan: via the home city
    assert all(isinstance(x["price_kzt_max"], int) for x in legs if "price_kzt_max" in x)
    assert "price_kzt_min" in legs[2] and "price_kzt_max" in legs[2]  # the flight has a price

    # the chat tools: no outside_area for these places, the brief holds the dates and the stay
    events, llm = seen["t6"]
    assert not any(has_key(r, "outside_area") for r in tool_results(llm))
    for key in ("t1", "t2", "t3", "t4", "t5"):
        assert not any(has_key(r, "outside_area") for r in tool_results(seen[key][1]))
    brief = (await owner.env.client.get("/v1/chats/%s" % owner.id, headers=owner.headers)).json()
    assert brief["brief"]["dated_wishes"] == [
        {"wish": "Шымбулак", "date": day(0)},
        {"wish": "Чарынский каньон", "date": day(2)},
    ]
    assert brief["brief"]["stay_wishes"] == [{"wish": "Кольсайские озёра", "stay": "overnight"}]
    count = await fetch_one(
        owner.conn, "SELECT count(*) AS n FROM analytics_events WHERE name = 'wish_outside_area'"
    )
    assert count["n"] == 0

    # the built trip: Charyn on its date, a night in Saty, Turkistan a transfer day
    ready = event(events, "route_ready")
    assert ready["must_have_unmet"] == []
    trip = (
        await owner.env.client.get("/v1/trips/%s" % ready["trip_id"], headers=owner.headers)
    ).json()
    days = trip["days"]
    assert len(days) == 6
    names = [[i["place"]["name"] for i in d["items"]] for d in days]
    assert any("Charyn" in n or "Чарын" in n for n in names[2])  # «послезавтра»
    assert any("Shymbulak" in n or "Шымбулак" in n for n in names[0])  # «сегодня»
    assert "Saty" in [d["overnight"]["city"]["en"] for d in days if d["overnight"]]
    assert days[-1]["kind"] == "transfer"
    assert days[-1]["legs"][0]["intercity"]["mode"] in ("plane", "train", "bus")

    # what the model gets to explain the plan: transfer days, overnights, the moves
    plan = next(r for r in tool_results(llm) if r.get("ok") and "days" in r and "budget" in r)
    facts = {d["date"]: d for d in plan["days"]}
    assert facts[days[-1]["date"]].get("transfer_day") is True
    assert facts[days[-1]["date"]]["moves_between_cities"][0]["to"] in ("Туркестан", "Turkistan")
    assert any(d.get("overnight_in") == "Saty" for d in plan["days"])  # the chat is in English
    from app.chat.build_tool import EXPLAIN

    assert "overnight_in" in EXPLAIN and "moves_between_cities" in EXPLAIN


async def test_the_live_route_is_stored_and_ordinary_legs_have_no_intercity(owner):
    """Two places of the city: the leg is as before Ш-62, no `intercity` key."""
    await turn(
        owner.env, owner.headers, owner.id,
        brief_step(must_haves=["Шымбулак", "Чарынский каньон"]),
    )  # fmt: skip
    route = await live(owner.env, owner.headers, owner.id)
    assert route["legs"][0]["intercity"] is True and route["legs"][0]["mode"] in ("car", "tour")
    # a re-read of the stored route gives the same leg (stored in chat_live_stops)
    again = await live(owner.env, owner.headers, owner.id)
    assert again == route
    row = await fetch_one(
        owner.conn,
        "SELECT leg_intercity, leg_mode FROM chat_live_stops WHERE ord = 2",
    )
    assert row["leg_intercity"] is True and row["leg_mode"] in ("car", "tour")


async def test_a_place_with_no_data_is_still_outside_area_and_an_unknown_place_is_no_place(owner):
    """Astana is a known place Jol has no data for (outside_area, counted); a made-up place is a
    wish without a place (no_place), exactly as before."""
    events, llm = await turn(
        owner.env, owner.headers, owner.id,
        brief_step(
            start_date=day(1), end_date=day(3), budget_kzt=400000, has_accommodation=True,
            must_haves=["Астана", "Zzzqx Moscow Tower"],
        ),
        Step(tool_calls=[call("build_trip", {})]),
    )  # fmt: skip
    first = next(r for r in tool_results(llm) if "outside_area" in r and "brief" in r)
    assert [x["id"] for x in first["outside_area"]] == ["astana"]
    count = await fetch_one(
        owner.conn,
        "SELECT count(*) AS n FROM analytics_events WHERE name = 'wish_outside_area'",
    )
    assert count["n"] == 1
    unmet = {u["wish"]: u["reason"] for u in event(events, "route_ready")["must_have_unmet"]}
    assert unmet["Астана"] == "outside_area"
    assert unmet["Zzzqx Moscow Tower"] == "no_place"
    assert (await live(owner.env, owner.headers, owner.id)) is None  # nothing to draw


async def test_search_places_finds_the_far_places_of_the_country(world, chat_env):  # noqa: F811
    from app.chat import tools
    from tests.conftest import TransactionalDatabase

    db = TransactionalDatabase(world)
    found, pins = await tools.search_places(db, tools.SearchPlacesArgs(query="Чарын"), "ru")
    assert [p["name"] for p in pins] == ["Чарынский каньон"] and "outside_area" not in found
    assert found["far"]["id"] == "charyn"
    found, pins = await tools.search_places(db, tools.SearchPlacesArgs(query="Астана"), "ru")
    assert pins == [] and found["outside_area"]["id"] == "astana"


# --- the leg rule on its own ------------------------------------------------------------------
def option(mode, minutes, low, high, **extra):
    base = {
        "mode": mode, "duration_s_max": minutes * 60, "duration_s": minutes * 60,
        "cost_kzt_min": low, "cost_kzt_max": high, "approximate": True, "schedule": None,
    }  # fmt: skip
    return dict(base, **extra)


SETTINGS = ctry.Settings(
    local_radius_km=60, group_radius_km=150, transfer_min_km=400, day_trip_max_oneway_h=3,
    transfer_budget_share=0.5, night_departure_min=1200, stay_search_km=40, max_outing_days=4,
    fallback_road_kmh=60,
)  # fmt: skip
ALMATY = (43.2389, 76.9455)
TURKISTAN = YASAWI


def test_a_transfer_is_the_fastest_affordable_public_way():
    raw = [
        option("plane", 270, 20000, 50000),
        option("train", 1100, 9000, 14000),
        option("bus", 1300, 8000, 11000),
        option("car", 700, 90000, 130000, distance_m=1_000_000),
        option("taxi", 700, 300000, 400000),
    ]
    leg = live_route.pick_intercity_leg(raw, ALMATY, TURKISTAN, SETTINGS, 600_000)
    assert leg == {
        "mode": "plane", "duration_s": 270 * 60, "distance_m": leg["distance_m"],
        "intercity": True, "price_kzt_min": 20000, "price_kzt_max": 50000,
    }  # fmt: skip
    assert 650_000 < leg["distance_m"] < 750_000  # the straight line, the plane has none
    # a small budget: the plane is not affordable (50 000 > 50% of 60 000), the train is
    cheap = live_route.pick_intercity_leg(raw, ALMATY, TURKISTAN, SETTINGS, 60_000)
    assert cheap["mode"] == "train"
    # the bus has the contract's name
    only_bus = live_route.pick_intercity_leg([raw[2]], ALMATY, TURKISTAN, SETTINGS, None)
    assert only_bus["mode"] == "bus_intercity"


def test_an_outing_is_a_road_and_a_taxi_is_never_offered():
    near = (43.325, 79.0586)  # Charyn, ~190 km: under transfer_min_km
    raw = [
        option("taxi", 170, 60000, 80000, distance_m=200_000, recommended=True),
        option("car", 180, 9000, 12000, distance_m=200_000),
        option("plane", 60, 1, 2),
    ]
    leg = live_route.pick_intercity_leg(raw, ALMATY, near, SETTINGS, 600_000)
    assert leg["mode"] == "car" and leg["distance_m"] == 200_000
    assert leg["price_kzt_min"] == 9000 and leg["price_kzt_max"] == 12000
    assert (
        live_route.pick_intercity_leg([option("taxi", 1, 1, 1)], ALMATY, near, SETTINGS, None)
        is None
    )


def test_an_unknown_price_is_left_out_not_invented():
    leg = live_route.pick_intercity_leg(
        [option("train", 600, None, None)], ALMATY, TURKISTAN, SETTINGS, 100
    )
    assert leg["mode"] == "train" and "price_kzt_min" not in leg and "price_kzt_max" not in leg


# --- edits keep intercity legs ----------------------------------------------------------------
async def turkistan_trip(chat_env, world):  # noqa: F811
    """A trip whose last day is a transfer with TWO stops in Turkistan."""
    await add(world, "Каравансарай Туркестана", "Turkistan Caravanserai", YASAWI[1] + 0.01,
              YASAWI[0] + 0.005, "historic", typical_visit_min=60)  # fmt: skip
    chat_env.app.state.routing_provider = RoadRouter()
    headers = await sign_in(world, "edit62@example.com")
    chat = await new_chat(chat_env, headers)
    events, _ = await turn(
        chat_env, headers, chat["id"],
        brief_step(
            start_date=day(3), end_date=day(5), budget_kzt=600000, has_accommodation=True,
            must_haves=["мавзолей Ходжи Ахмеда Ясави", "Каравансарай Туркестана"],
        ),
        Step(tool_calls=[call("build_trip", {})]),
    )  # fmt: skip
    trip_id = event(events, "route_ready")["trip_id"]
    return headers, trip_id


async def get_trip(chat_env, headers, trip_id):
    return (await chat_env.client.get("/v1/trips/%s" % trip_id, headers=headers)).json()


def far_day(trip):
    return next(d for d in trip["days"] if any(x["intercity"] for x in d["legs"]))


async def test_removing_a_stop_keeps_the_intercity_leg(chat_env, world):  # noqa: F811
    headers, trip_id = await turkistan_trip(chat_env, world)
    trip = await get_trip(chat_env, headers, trip_id)
    day_ = far_day(trip)
    assert len(day_["items"]) == 2 and day_["legs"][0]["intercity"]["mode"] in ("plane", "train")
    # remove the SECOND stop: the first leg (the flight) stays
    response = await chat_env.client.post(
        "/v1/trips/%s/items/%s/remove" % (trip_id, day_["items"][1]["id"]),
        headers=headers, json={"force": True},
    )  # fmt: skip
    assert response.status_code == 200, response.text
    after = far_day(await get_trip(chat_env, headers, trip_id))
    assert len(after["items"]) == 1
    leg = after["legs"][0]
    assert leg["intercity"] is not None and leg["intercity"]["mode"] == leg["chosen_mode"]
    assert leg["from_item_id"] is None and leg["travel_s"] > 3 * 3600
    assert set(leg["intercity"]) == {
        "mode", "from_city", "to_city", "approximate", "price_kzt_min", "price_kzt_max",
    }  # fmt: skip
    assert leg["intercity"]["to_city"]["en"] == "Turkistan"


async def test_removing_the_first_stop_keeps_the_intercity_leg(chat_env, world):  # noqa: F811
    headers, trip_id = await turkistan_trip(chat_env, world)
    day_ = far_day(await get_trip(chat_env, headers, trip_id))
    mode = day_["legs"][0]["chosen_mode"]
    response = await chat_env.client.post(
        "/v1/trips/%s/items/%s/remove" % (trip_id, day_["items"][0]["id"]),
        headers=headers, json={"force": True},
    )  # fmt: skip
    assert response.status_code == 200, response.text
    after = far_day(await get_trip(chat_env, headers, trip_id))
    assert len(after["items"]) == 1  # the day now starts with the other stop, still by the flight
    assert after["legs"][0]["intercity"]["mode"] == mode == after["legs"][0]["chosen_mode"]


async def test_choosing_another_way_updates_the_intercity_block(chat_env, world):  # noqa: F811
    headers, trip_id = await turkistan_trip(chat_env, world)
    leg = far_day(await get_trip(chat_env, headers, trip_id))["legs"][0]
    other = "train" if leg["chosen_mode"] != "train" else "plane"
    response = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (trip_id, leg["id"]), headers=headers, json={"mode": other}
    )
    assert response.status_code == 200, response.text
    chosen = far_day(await get_trip(chat_env, headers, trip_id))["legs"][0]
    assert chosen["chosen_mode"] == other and chosen["intercity"]["mode"] == other  # in step
    option = next(o for o in chosen["options"] if o["mode"] == other)
    assert chosen["intercity"]["price_kzt_max"] == option["cost_kzt_max"]


async def test_replacing_a_stop_keeps_the_intercity_leg(chat_env, world):  # noqa: F811
    headers, trip_id = await turkistan_trip(chat_env, world)
    day_ = far_day(await get_trip(chat_env, headers, trip_id))
    spare = await add(
        world, "Музей Туркестана", "Turkistan Museum", YASAWI[1] - 0.01, YASAWI[0],
        "museum", typical_visit_min=60,
    )  # fmt: skip
    response = await chat_env.client.post(
        "/v1/trips/%s/items/%s/replace" % (trip_id, day_["items"][1]["id"]),
        headers=headers, json={"place_id": str(spare), "force": True},
    )  # fmt: skip
    assert response.status_code == 200, response.text
    after = far_day(await get_trip(chat_env, headers, trip_id))
    assert after["legs"][0]["intercity"] is not None
    assert [i["place"]["name"] for i in after["items"]][1] in ("Музей Туркестана",
                                                                "Turkistan Museum")  # fmt: skip


async def test_the_offline_copy_carries_day_facts_and_intercity_legs(chat_env, world):  # noqa: F811
    headers, trip_id = await turkistan_trip(chat_env, world)
    trip = await get_trip(chat_env, headers, trip_id)
    response = await chat_env.client.get("/v1/trips/%s/offline" % trip_id, headers=headers)
    assert response.status_code == 200, response.text
    offline = response.json()
    for d, full in zip(offline["days"], trip["days"]):
        assert set(d) == {"date", "kind", "overnight", "items", "legs"}
        assert d["kind"] == full["kind"] and d["overnight"] == full["overnight"]
        for leg in d["legs"]:
            assert "intercity" in leg
    assert offline["days"][-1]["kind"] == "transfer"
    far = [leg for d in offline["days"] for leg in d["legs"] if leg["intercity"]]
    assert far and set(far[0]["intercity"]) == {
        "mode", "from_city", "to_city", "approximate", "price_kzt_min", "price_kzt_max",
    }  # fmt: skip
    ordinary = [leg for d in offline["days"] for leg in d["legs"] if not leg["intercity"]]
    assert all(leg["intercity"] is None for leg in ordinary)


# --- the prompt -------------------------------------------------------------------------------
@pytest.mark.parametrize("locale", ["ru", "en"])
def test_prompt_v8_has_the_country_rules_and_v7_is_untouched(locale):
    latest = prompts.load_prompt(prompts.TRIP_BRIEF, locale)
    assert latest.version == 8
    text = latest.render()
    for word in ("dated_wishes", "stay_wishes", "overnight", "transfer_day", "outside_area",
                 "moves_between_cities", "update_trip_brief"):  # fmt: skip
        assert word in text, word
    assert ("ночёвк" if locale == "ru" else "stay a night") in text
    assert ("только {{region}}" not in text) and "{{" not in text
    old = prompts.load_prompt(prompts.TRIP_BRIEF, locale, version=7).text
    assert "dated_wishes" not in old  # a released version is never edited
