"""Live route of a chat (Ш-54): stops, alternatives, legs, choose, restore, removal, generator."""

from types import SimpleNamespace

import pytest

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


async def turn(env, headers, chat_id, *calls):
    use(env, steps=[Step(tool_calls=list(calls)), Step(text=["ok"])])
    response = await say(env, headers, chat_id)
    assert response.status_code == 200, response.text
    return parse_sse(response.text)


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
    names = [n for n, _ in events]
    assert names == ["brief_updated", "map_places", "live_route", "text_delta", "done"]
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

    # old clients still get the best match per new wish
    pins = [d for n, d in events if n == "map_places"][0]
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


async def test_same_wish_again_emits_no_live_route(world):
    await add_wishes(world, CHINESE)
    events = await add_wishes(world, CHINESE.lower())
    assert live_events(events) == []  # nothing changed


async def test_unknown_wish_gets_no_stop(world):
    events = await add_wishes(world, "Nonexistent Cuisine XYZ")
    assert live_events(events) == [] and "map_places" not in [n for n, _ in events]
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
