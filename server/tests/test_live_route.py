"""Live route of a chat (Ш-54): stops, alternatives, legs, choose, restore, removal, generator."""

import asyncio
from types import SimpleNamespace

import pytest
from psycopg.rows import dict_row

from app.chat import api as chat_api
from app.chat import live_route
from app.db import fetch_all, fetch_one
from app.providers.llm.fake import Step
from app.routing import FakeRouter
from tests.conftest import parse_sse
from tests.test_chat import call, new_chat, say, sign_in, use
from tests.test_places import add_place, load_categories
from tests.test_trips import brief_call

CHINESE = "Chinese"
PARK = "First President's Park"
BAZAAR = "Green Bazaar"

# lon, lat. The Chinese places are in one block; the park is ~3.5 km away (no 20-minute walk),
# the bazaar ~700 m from the park (a walk).
PLACES = [
    ("Chinese Dragon", 76.9300, 43.2400, "cafe_chinese", 90),
    ("Chinese Lotus", 76.9310, 43.2402, "cafe_chinese", 70),
    ("Chinese Panda", 76.9320, 43.2404, "cafe_chinese", 50),
    ("Chinese Wok", 76.9330, 43.2406, "cafe_chinese", 10),
    (PARK, 76.9700, 43.2100, "park", 80),
    (BAZAAR, 76.9750, 43.2150, "market", 60),
]


async def seed(conn):
    await load_categories(conn)
    await conn.execute(
        "INSERT INTO transport_tariffs "
        "(mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, source)"
        " VALUES ('taxi', '2026-01-01', 500, 0, 150, 'test')"
    )
    ids = {}
    for name, lon, lat, cat, pop in PLACES:
        ids[name] = await add_place(conn, name, lon, lat, cat, "active", pop)
    return ids


async def stored_route(env, headers, chat_id):
    detail = await env.client.get("/v1/chats/%s" % chat_id, headers=headers)
    return detail.json()["live_route"]


async def settle(env, headers, chat_id, response, before):
    """Events of a finished turn, with what Ш-64 moved out of the message stream added back.

    The live route is built in the background now, so the message stream carries it before `done`
    only when the pass happened to end first. The tests below are about the route, not about that
    timing: wait for the background pass, and if the stored route changed in this turn and the
    stream did not carry it, append it as `live_route` (as the stream did before Ш-64)."""
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    await chat_api.scheduler_of(env.app).drain()
    after = await stored_route(env, headers, chat_id)
    if not live_events(events) and after != before:
        events.append(("live_route", after or {"stops": [], "legs": []}))
    return events


async def turn(env, headers, chat_id, *calls):
    use(env, steps=[Step(tool_calls=list(calls)), Step(text=["ok"])])
    before = await stored_route(env, headers, chat_id)
    response = await say(env, headers, chat_id)
    return await settle(env, headers, chat_id, response, before)


def live_events(events):
    return [data for name, data in events if name == "live_route"]


@pytest.fixture
async def world(chat_env, conn):
    ids = await seed(conn)
    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    return SimpleNamespace(env=chat_env, conn=conn, ids=ids, headers=headers, chat=chat)


async def add_wishes(w, *wishes):
    events = await turn(
        w.env, w.headers, w.chat["id"], call("update_trip_brief", {"must_haves": list(wishes)})
    )
    return events


async def get_chat(w, headers=None):
    response = await w.env.client.get("/v1/chats/%s" % w.chat["id"], headers=headers or w.headers)
    assert response.status_code == 200, response.text
    return response.json()


async def choose(w, ord_, place_id, headers=None, chat_id=None):
    return await w.env.client.post(
        "/v1/chats/%s/live-route/choose" % (chat_id or w.chat["id"]),
        headers=headers or w.headers,
        json={"ord": ord_, "place_id": str(place_id)},
    )


async def test_new_wishes_give_stops_alternatives_and_legs(world):
    events = await add_wishes(world, CHINESE, PARK, BAZAAR)
    names = [n for n, _ in events if n != "map_places"]
    assert names[:2] == ["brief_updated", "live_route_status"]  # Ш-64: building, in the background
    assert [n for n in names if n == "text_delta"] == ["text_delta"]
    route = live_events(events)[0]

    stops = route["stops"]
    assert [(s["ord"], s["wish"]) for s in stops] == [(1, CHINESE), (2, PARK), (3, BAZAAR)]
    ids = world.ids
    assert stops[0]["place"] == {
        "id": str(ids["Chinese Dragon"]),
        "name": "Chinese Dragon",
        "category": "cafe_chinese",
        "lat": pytest.approx(43.24),
        "lon": pytest.approx(76.93),
    }
    # best = stop, the next two best = alternatives (max 3 places per wish)
    assert [a["id"] for a in stops[0]["alternatives"]] == [
        str(ids["Chinese Lotus"]),
        str(ids["Chinese Panda"]),
    ]
    assert stops[1]["alternatives"] == [] and stops[2]["alternatives"] == []

    legs = route["legs"]
    assert [(leg["from_ord"], leg["to_ord"], leg["mode"]) for leg in legs] == [
        (1, 2, "car"),  # far: no 20-minute walk, no transit network -> car
        (2, 3, "walk"),  # ~700 m
    ]
    assert all(isinstance(leg["duration_s"], int) and leg["distance_m"] > 0 for leg in legs)
    assert legs[1]["duration_s"] <= 20 * 60

    # old clients still get the best match per new wish, when the pass ended before `done`
    for pins in [d for n, d in events if n == "map_places"]:
        assert pins["reason"] == "must_have"
        assert [(p["name"], p["must_have"]) for p in pins["places"]] == [
            ("Chinese Dragon", CHINESE),
            (PARK, PARK),
            (BAZAAR, BAZAAR),
        ]


async def test_get_chat_restores_the_live_route_or_null(world):
    assert (await get_chat(world))["live_route"] is None
    events = await add_wishes(world, CHINESE, PARK)
    assert (await get_chat(world))["live_route"] == live_events(events)[0]


async def test_only_new_wishes_are_searched_and_old_legs_are_kept(world, monkeypatch):
    first = live_events(await add_wishes(world, CHINESE, PARK))[0]
    calls = []
    original = live_route.compute_leg

    async def spy(*args):
        calls.append(args[2:])
        return await original(*args)

    monkeypatch.setattr(live_route, "compute_leg", spy)
    second = live_events(await add_wishes(world, BAZAAR))[0]
    assert [s["wish"] for s in second["stops"]] == [CHINESE, PARK, BAZAAR]
    assert second["stops"][:2] == first["stops"]  # untouched stops are identical
    assert second["legs"][0] == first["legs"][0]
    assert len(calls) == 1  # only the new leg 2 -> 3 was computed


async def test_same_wish_again_changes_nothing(world):
    first = live_events(await add_wishes(world, CHINESE))[0]
    events = await add_wishes(world, CHINESE.lower())
    assert all(route == first for route in live_events(events))  # at most the same route again
    assert (await get_chat(world))["live_route"] == first


async def test_unknown_wish_gets_no_stop(world):
    events = await add_wishes(world, "Nonexistent Cuisine XYZ")
    assert all(r == {"stops": [], "legs": []} for r in live_events(events))
    assert "map_places" not in [n for n, _ in events]
    assert (await get_chat(world))["live_route"] is None


async def test_removing_a_wish_drops_its_stop_and_recomputes_legs(world):
    first = live_events(await add_wishes(world, CHINESE, PARK, BAZAAR))[0]
    events = await turn(
        world.env,
        world.headers,
        world.chat["id"],
        call("update_trip_brief", {"remove_must_haves": [PARK]}),
    )
    route = live_events(events)[0]
    assert [(s["ord"], s["wish"]) for s in route["stops"]] == [(1, CHINESE), (2, BAZAAR)]
    assert [(leg["from_ord"], leg["to_ord"]) for leg in route["legs"]] == [(1, 2)]
    assert route["legs"][0] != first["legs"][0]
    assert route["legs"][0]["mode"] == "car"  # Chinese block -> the bazaar is far
    assert "map_places" not in [n for n, _ in events]

    gone = await turn(
        world.env,
        world.headers,
        world.chat["id"],
        call("update_trip_brief", {"remove_must_haves": [CHINESE, BAZAAR]}),
    )
    assert live_events(gone) == [{"stops": [], "legs": []}]
    assert (await get_chat(world))["live_route"] is None


async def test_choose_makes_an_alternative_the_stop(world):
    route = live_events(await add_wishes(world, CHINESE, PARK))[0]
    lotus = world.ids["Chinese Lotus"]
    response = await choose(world, 1, lotus)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stops"][0]["place"]["id"] == str(lotus)
    # the old stop place is offered as an alternative; the chosen one is no longer
    assert [a["id"] for a in body["stops"][0]["alternatives"]] == [
        str(world.ids["Chinese Panda"]),
        str(world.ids["Chinese Dragon"]),
    ]
    assert body["stops"][1] == route["stops"][1]
    assert len(body["legs"]) == 1 and body["legs"][0]["mode"] == "car"
    assert body["legs"][0] != route["legs"][0]  # recomputed from the new place
    assert (await get_chat(world))["live_route"] == body  # persisted

    again = await choose(world, 1, lotus)  # the current stop: unchanged
    assert again.status_code == 200 and again.json() == body
    back = await choose(world, 1, world.ids["Chinese Dragon"])
    assert back.json()["stops"][0]["place"]["id"] == str(world.ids["Chinese Dragon"])


async def test_choose_errors(world, conn):
    await add_wishes(world, CHINESE, PARK)
    foreign = world.ids[BAZAAR]
    wrong = await choose(world, 1, foreign)  # not an alternative of stop 1
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "validation_error"
    assert (await choose(world, 2, world.ids["Chinese Lotus"])).status_code == 422
    assert (await choose(world, 9, world.ids["Chinese Lotus"])).status_code == 404
    assert (await choose(world, 0, world.ids["Chinese Lotus"])).status_code == 422  # ord >= 1
    other = await sign_in(conn, "b@example.com")
    assert (await choose(world, 1, world.ids["Chinese Lotus"], headers=other)).status_code == 404
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await choose(world, 1, world.ids["Chinese Lotus"], chat_id=unknown)).status_code == 404
    anon = await world.env.client.post(
        "/v1/chats/%s/live-route/choose" % world.chat["id"],
        json={"ord": 1, "place_id": str(world.ids["Chinese Lotus"])},
    )
    assert anon.status_code == 401
    assert (await get_chat(world))["live_route"]["stops"][0]["place"]["name"] == "Chinese Dragon"


async def test_choose_is_refused_while_a_turn_runs(world, conn):
    await add_wishes(world, CHINESE)
    await conn.execute(
        "UPDATE chats SET turn_lease_until = clock_timestamp() + interval '1 minute' WHERE id = %s",
        (world.chat["id"],),
    )
    response = await choose(world, 1, world.ids["Chinese Lotus"])
    assert response.status_code == 409 and response.json()["error"]["code"] == "chat_busy"


async def test_locale_of_the_chat_picks_names(chat_env, conn):
    await load_categories(conn)
    place = await add_place(conn, "Парк", 76.95, 43.23, "park", "active", 50)
    await conn.execute("UPDATE places SET name_en = 'Park EN' WHERE id = %s", (place,))
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers, "en")
    await turn(chat_env, headers, chat["id"], call("update_trip_brief", {"must_haves": ["Парк"]}))
    detail = (await chat_env.client.get("/v1/chats/%s" % chat["id"], headers=headers)).json()
    assert detail["live_route"]["stops"][0]["place"]["name"] == "Park EN"


# --- leg rule -----------------------------------------------------------------------------------


def option(group, duration_s, distance_m=1000):
    return SimpleNamespace(group=group, duration_s=duration_s, distance_m=distance_m)


def test_leg_rule_walk_then_transit_then_car():
    pick = live_route.pick_leg
    assert pick([option("walk", 1200), option("taxi", 300)])["mode"] == "walk"  # exactly 20 min
    long_walk = option("walk", 1201)
    assert pick([long_walk, option("transit", 1500), option("taxi", 300)])["mode"] == "transit"
    assert pick([long_walk, option("taxi", 900), option("car", 800)]) == {
        "mode": "car",
        "duration_s": 800,
        "distance_m": 1000,
    }
    assert pick([long_walk])["mode"] == "walk"  # nothing else exists
    assert pick([]) is None


async def test_leg_is_left_out_when_routing_fails(world):
    class Down(FakeRouter):
        async def route(self, *args, **kwargs):
            from app.routing import RoutingUnavailable

            raise RoutingUnavailable("down")

        async def routes(self, *args, **kwargs):
            await self.route()

    world.env.app.state.routing_provider = Down()
    route = live_events(await add_wishes(world, CHINESE, PARK))[0]
    assert len(route["stops"]) == 2 and route["legs"] == []
    # healed on the next change: the leg is computed when the router works again
    world.env.app.state.routing_provider = FakeRouter()
    healed = live_events(await add_wishes(world, BAZAAR))[0]
    assert [(leg["from_ord"], leg["to_ord"]) for leg in healed["legs"]] == [(1, 2), (2, 3)]


# --- generator ----------------------------------------------------------------------------------


async def test_trip_generator_uses_the_chosen_place(chat_env, conn):
    from tests.test_trips import seed_world

    await seed_world(conn)
    extra = [
        await add_place(conn, "Плов Центр Юг", 76.9305, 43.2405, "cafe_oriental", "active", 5),
        await add_place(conn, "Плов Центр Север", 76.9306, 43.2406, "cafe_oriental", "active", 4),
    ]
    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    wish = "Плов Центр"
    events = await turn(
        chat_env,
        headers,
        chat["id"],
        brief_call(has_accommodation=True, must_haves=[wish]),
    )
    route = live_events(events)[0]
    stop = route["stops"][0]
    alts = {a["id"] for a in stop["alternatives"]}
    assert alts and alts <= {str(e) for e in extra}
    pick = sorted(alts)[0]

    response = await choose_via(chat_env, headers, chat["id"], 1, pick)
    assert response.status_code == 200, response.text

    await turn(chat_env, headers, chat["id"], call("build_trip", {}))
    rows = await fetch_all(
        conn,
        "SELECT i.place_id::text AS pid FROM trip_items i JOIN trips t ON t.id = i.trip_id "
        "WHERE t.chat_id = %s",
        (chat["id"],),
    )
    assert pick in {r["pid"] for r in rows}  # the chosen place is in the trip


async def choose_via(env, headers, chat_id, ord_, place_id):
    return await env.client.post(
        "/v1/chats/%s/live-route/choose" % chat_id,
        headers=headers,
        json={"ord": ord_, "place_id": place_id},
    )


async def test_select_candidates_puts_the_chosen_place_first(conn):
    from app.planner.candidates import select_candidates
    from tests.test_planner_candidates import brief as cand_brief
    from tests.test_trips import seed_world

    await seed_world(conn)
    chosen = await fetch_one(conn, "SELECT id FROM places WHERE name_ru = 'Столовая'")
    sel = await select_candidates(
        conn,
        cand_brief(must_haves=["Плов-центр"]),
        chosen_places={"плов-центр": chosen["id"]},
    )
    wish = sel.must_haves[0]
    assert wish.places[0].id == chosen["id"] and wish.how == "chosen"
    plain = await select_candidates(conn, cand_brief(must_haves=["Плов-центр"]))
    assert plain.must_haves[0].places[0].id != chosen["id"]


# --- races (Ш-63) --------------------------------------------------------------------------------

SUSHI = "Sushi"
RACE_PLACES = PLACES + [
    ("Sushi Alpha", 76.9500, 43.2500, "cafe_japanese", 90),
    ("Sushi Beta", 76.9510, 43.2502, "cafe_japanese", 70),
    ("Sushi Gamma", 76.9520, 43.2504, "cafe_japanese", 50),
]


class SlowRouter(FakeRouter):
    """Every route takes a moment, so concurrent requests really overlap."""

    async def route(self, from_point, to_point, mode):
        await asyncio.sleep(0.05)
        return await super().route(from_point, to_point, mode)


@pytest.fixture
async def race(committed_auth_db_url):
    """Real pool on a committed database: two requests really run on two connections."""
    from httpx import ASGITransport, AsyncClient
    from psycopg import AsyncConnection

    from app.auth import sessions
    from app.db import Database
    from app.main import create_app

    async with await AsyncConnection.connect(
        committed_auth_db_url, autocommit=True, row_factory=dict_row
    ) as setup:
        await load_categories(setup)
        ids = {}
        for name, lon, lat, cat, pop in RACE_PLACES:
            ids[name] = await add_place(setup, name, lon, lat, cat, "active", pop)
        tokens = await sessions.sign_in(setup, "email", "race@example.com", "en")
        chat = await fetch_one(
            setup,
            "INSERT INTO chats (user_id, locale) SELECT id, 'en' FROM users LIMIT 1 RETURNING id",
        )
    app = create_app()
    db = Database(committed_auth_db_url, min_size=1, max_size=8)
    app.state.db = db
    app.state.routing_provider = SlowRouter()
    await db.open()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(
            db=db,
            client=client,
            ids=ids,
            chat_id=chat["id"],
            headers={"Authorization": "Bearer %s" % tokens.access_token},
            router=app.state.routing_provider,
        )
    await db.close()
    async with await AsyncConnection.connect(committed_auth_db_url, autocommit=True) as cleanup:
        await cleanup.execute("TRUNCATE places, place_categories CASCADE")


async def race_choose(r, ord_, place_id):
    return await r.client.post(
        "/v1/chats/%s/live-route/choose" % r.chat_id,
        headers=r.headers,
        json={"ord": ord_, "place_id": str(place_id)},
    )


async def read_route(r):
    async with r.db.transaction() as conn:
        return await live_route.load(conn, r.chat_id, "en")


def place_ids(route):
    return [s["place"]["id"] for s in route["stops"]]


async def test_two_concurrent_chooses_on_different_stops_keep_both(race):
    await live_route.sync(race.db, race.chat_id, "en", race.router, [CHINESE, SUSHI])
    before = await read_route(race)
    assert [s["wish"] for s in before["stops"]] == [CHINESE, SUSHI]
    alt1 = before["stops"][0]["alternatives"][0]["id"]
    alt2 = before["stops"][1]["alternatives"][0]["id"]

    first, second = await asyncio.gather(race_choose(race, 1, alt1), race_choose(race, 2, alt2))
    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)

    after = await read_route(race)
    assert place_ids(after) == [alt1, alt2]  # neither choice was lost
    for stop, old in zip(after["stops"], before["stops"]):  # the old stops became alternatives
        assert len(stop["alternatives"]) == 2
        assert old["place"]["id"] in [a["id"] for a in stop["alternatives"]]
    assert [(g["from_ord"], g["to_ord"]) for g in after["legs"]] == [(1, 2)]


async def test_two_concurrent_chooses_on_one_stop_stay_consistent(race):
    await live_route.sync(race.db, race.chat_id, "en", race.router, [CHINESE])
    before = await read_route(race)
    everything = {before["stops"][0]["place"]["id"]} | {
        a["id"] for a in before["stops"][0]["alternatives"]
    }
    alt1, alt2 = [a["id"] for a in before["stops"][0]["alternatives"]]

    first, second = await asyncio.gather(race_choose(race, 1, alt1), race_choose(race, 1, alt2))
    assert (first.status_code, second.status_code) == (200, 200)

    after = await read_route(race)
    (stop,) = after["stops"]
    now = [stop["place"]["id"]] + [a["id"] for a in stop["alternatives"]]
    assert len(now) == 3 and set(now) == everything  # no place lost or duplicated
    assert stop["place"]["id"] in (alt1, alt2)


async def test_choose_and_sync_of_a_new_wish_do_not_lose_each_other(race):
    await live_route.sync(race.db, race.chat_id, "en", race.router, [CHINESE])
    before = await read_route(race)
    alt = before["stops"][0]["alternatives"][0]["id"]

    response, _ = await asyncio.gather(
        race_choose(race, 1, alt),
        live_route.sync(race.db, race.chat_id, "en", race.router, [CHINESE, SUSHI]),
    )
    assert response.status_code == 200, response.text

    after = await read_route(race)
    assert [s["wish"] for s in after["stops"]] == [CHINESE, SUSHI]  # the new stop survived
    assert after["stops"][0]["place"]["id"] == alt  # and so did the choice
    assert len(after["legs"]) == 1


# --- real Valhalla (Ш-63) ---------------------------------------------------------------------

REPUBLIC_SQUARE = (43.2389, 76.9452)  # lat, lon
CENTRAL_MOSQUE = (43.2427, 76.9467)  # ~0.8 km on foot
PANFILOV_PARK = (43.2587, 76.9565)  # ~3 km: more than a 20-minute walk
MEDEU = (43.1575, 77.0589)  # ~14 km, far outside walking


@pytest.fixture
async def valhalla():
    """Router on the Valhalla of docker-compose; skips the test when it is not reachable."""
    import httpx

    from app.config import get_settings
    from app.routing import ValhallaRouter

    url = get_settings().valhalla_url or "http://127.0.0.1:8002"
    try:
        async with httpx.AsyncClient(timeout=2.0) as http:
            if (await http.get(url.rstrip("/") + "/status")).status_code != 200:
                pytest.skip("Valhalla at %s is not healthy" % url)
    except httpx.HTTPError:
        pytest.skip("Valhalla at %s is not reachable" % url)
    router = ValhallaRouter(url)
    yield router
    await router.aclose()


async def real_leg(conn, router, origin, destination):
    from tests.conftest import TransactionalDatabase

    await conn.execute(
        "INSERT INTO transport_tariffs (mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, "
        "source) VALUES ('taxi', '2026-01-01', 500, 0, 150, 'test')"
    )
    return await live_route.compute_leg(TransactionalDatabase(conn), router, origin, destination)


async def test_real_valhalla_short_leg_is_a_walk(conn, valhalla):
    leg = await real_leg(conn, valhalla, REPUBLIC_SQUARE, CENTRAL_MOSQUE)
    assert leg is not None and leg["mode"] == "walk"
    assert 300 <= leg["duration_s"] <= 20 * 60  # 0.8 km at walking speed
    assert 500 <= leg["distance_m"] <= 1500


async def test_real_valhalla_mid_leg_is_a_car_when_the_walk_is_long(conn, valhalla):
    leg = await real_leg(conn, valhalla, REPUBLIC_SQUARE, PANFILOV_PARK)
    assert leg is not None and leg["mode"] == "car"  # the walk takes over 20 minutes
    assert 2000 <= leg["distance_m"] <= 8000
    assert 3 * 60 <= leg["duration_s"] <= 25 * 60


async def test_real_valhalla_far_leg_is_a_car_with_sane_time(conn, valhalla):
    leg = await real_leg(conn, valhalla, REPUBLIC_SQUARE, MEDEU)
    assert leg is not None and leg["mode"] == "car"
    assert 8000 <= leg["distance_m"] <= 30000
    assert 10 * 60 <= leg["duration_s"] <= 90 * 60


async def test_real_valhalla_leg_in_a_live_route(world, valhalla):
    """Through the chat: the leg between two stops comes from the real engine."""
    world.env.app.state.routing_provider = valhalla
    route = live_events(await add_wishes(world, CHINESE, PARK))[0]
    (leg,) = route["legs"]
    assert (leg["from_ord"], leg["to_ord"], leg["mode"]) == (1, 2, "car")  # ~5 km, long walk
    assert 5 * 60 <= leg["duration_s"] <= 40 * 60
    assert 3000 <= leg["distance_m"] <= 12000
    stored = (await get_chat(world))["live_route"]["legs"]
    assert stored == route["legs"]
