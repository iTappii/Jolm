"""The AI recommends by itself (Ш-68): anchor, signals, "best for a tourist" order, privacy."""

import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.chat import tools
from app.chat.location import Location
from app.live import clock
from app.places import recommend
from app.providers.llm import FakeLLM
from app.providers.llm.fake import FakeToolCall, Step
from app.regions import default_region
from tests.conftest import parse_sse
from tests.test_chat import new_chat, sign_in
from tests.test_dishes import GREEN_BAZAAR, INSTALL, Db
from tests.test_places import add_place, load_categories

SEED = Path(__file__).resolve().parents[2] / "data" / "seed" / "dishes.sql"
# Monday 2026-11-23 20:00 in Almaty (UTC+5)
NOW = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)
ME = (43.26013, 76.95027)  # the tourist: lat, lon (exact numbers must never reach the model)
ME_TEXT = ("43.26013", "76.95027")


@pytest.fixture(autouse=True)
def fixed_clock():
    clock.set_clock(lambda: NOW)
    yield
    clock.set_clock(None)


async def add_hours(conn, place_id, opens, closes, weekdays=range(7)):
    for day in weekdays:
        await conn.execute(
            "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES (%s, %s, %s, %s)",
            (place_id, day, opens, closes),
        )


async def seed(conn):
    await load_categories(conn)
    await conn.execute(SEED.read_text(encoding="utf-8"))
    ids = {}
    # name matches for "донер" (the same dish tier), different signals
    for name, lon, lat, pop in [
        ("Донер Рядом", 76.9510, 43.2605, 0),  # ~100 m from the tourist, unknown fame
        ("Донер Знаменитый", 76.9560, 43.2640, 90),  # ~700 m, very popular
        ("Донер Закрыт", 76.9505, 43.2602, 90),  # right here, popular, but closed now
        ("Донер Далеко", 77.0500, 43.3300, 95),  # ~11 km
    ]:
        ids[name] = await add_place(conn, name, lon, lat, "cafe_fast_food", "active", pop)
    await add_hours(conn, ids["Донер Знаменитый"], time(9, 0), time(23, 0))
    await add_hours(conn, ids["Донер Закрыт"], time(9, 0), time(18, 0))
    await add_hours(conn, ids["Донер Далеко"], time(0, 0), time(23, 59))
    await conn.execute(
        "UPDATE places SET address_ru = 'пр. Абая, 10', avg_check_kzt = 2500 WHERE id = %s",
        (ids["Донер Знаменитый"],),
    )
    return ids


@pytest.fixture
async def world(conn):
    ids = await seed(conn)
    return SimpleNamespace(conn=conn, db=Db(conn), ids=ids)


def by_name(result):
    return {p["name"]: p for p in result["places"]}


def order(result):
    return [p["name"] for p in result["places"]]


# ------------------------------------------------------------------------------ the anchor


def test_anchor_precedence_location_then_lodging_then_region_centre():
    region = default_region()
    lodging = (43.2500, 76.9400)
    assert recommend.choose_anchor(ME, lodging).source == recommend.SOURCE_LOCATION
    assert recommend.choose_anchor(None, lodging).source == recommend.SOURCE_LODGING
    centre = recommend.choose_anchor()
    assert centre.source == recommend.SOURCE_REGION
    assert (centre.lat, centre.lon) == region.centre
    chosen = recommend.choose_anchor(ME, lodging)
    assert (chosen.lat, chosen.lon) == ME


@pytest.mark.parametrize(
    "point", [(51.1694, 71.4491), (95.0, 10.0), (float("nan"), 76.9), (43.2, float("inf"))]
)
def test_a_location_outside_the_region_or_invalid_falls_back(point):
    anchor = recommend.choose_anchor(point, None)
    assert anchor.source == recommend.SOURCE_REGION
    lodging = recommend.choose_anchor(point, (43.25, 76.94))
    assert lodging.source == recommend.SOURCE_LODGING


def test_lodging_point_reads_coordinates_from_the_brief_only_when_valid():
    assert recommend.lodging_point({"lodging": {"lat": 43.25, "lon": 76.94}}) == (43.25, 76.94)
    assert recommend.lodging_point({"lodging": {"lat": 143.25, "lon": 76.94}}) is None
    assert recommend.lodging_point({"has_accommodation": True}) is None
    assert recommend.lodging_point(None) is None


def test_the_anchor_and_location_do_not_print_coordinates():
    anchor = recommend.choose_anchor(ME)
    assert "43.26013" not in repr(anchor) and "76.95027" not in repr(anchor)
    location = Location(lat=ME[0], lon=ME[1])
    assert "43.26013" not in repr(location) and "43.26013" not in str(location)


# -------------------------------------------------------------------- ranking and signals


def test_blend_prefers_near_open_and_known_places_and_a_dish_tier_beats_all_signals():
    near_open = recommend.score(50, 200, True, True, True)
    far_open = recommend.score(50, 6000, True, True, True)
    near_closed = recommend.score(50, 200, False, True, True)
    unknown_hours = recommend.score(50, 200, None, False, True)
    assert near_open > far_open
    assert near_open > unknown_hours > near_closed
    assert recommend.score(90, 200, True, True, True) > recommend.score(10, 200, True, True, True)
    weights = (
        recommend.W_POPULARITY + recommend.W_DISTANCE + recommend.W_OPEN + recommend.W_COMPLETE
    )
    assert weights == pytest.approx(1.0)
    best_related = recommend.score(100, 0, True, True, True, tier=3)
    worst_cuisine = recommend.score(0, 99_000, False, False, False, tier=2)
    assert worst_cuisine > best_related


async def test_search_orders_best_for_a_tourist_and_carries_signals(world):
    anchor = recommend.choose_anchor(ME)
    result, pins = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="донер"), "ru", anchor
    )
    assert order(result) == ["Донер Знаменитый", "Донер Рядом", "Донер Закрыт", "Донер Далеко"]
    assert [p["name"] for p in pins] == order(result)
    famous = by_name(result)["Донер Знаменитый"]
    assert famous["match"] == "name" and famous["popularity"] == 90
    assert famous["open_now"] is True and famous["closes_at"] == "23:00"
    assert famous["price_level"] == 1 and famous["avg_check_kzt"] == 2500
    assert famous["address"] == "пр. Абая, 10" and famous["category"] == "Фастфуд"
    assert famous["distance_m"] % 100 == 0 and 500 <= famous["distance_m"] <= 900
    assert by_name(result)["Донер Закрыт"]["open_now"] is False
    assert "closes_at" not in by_name(result)["Донер Закрыт"]
    assert by_name(result)["Донер Далеко"]["open_24h"] is True
    assert result["anchor"] == "tourist_location" and "Recommend" in result["ranking"]


async def test_missing_data_means_missing_signals_not_made_up_ones(world):
    result, _ = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="донер"), "en", recommend.choose_anchor(ME)
    )
    bare = by_name(result)["Донер Рядом"]
    for key in ("popularity", "open_now", "closes_at", "price_level", "avg_check_kzt", "address"):
        assert key not in bare
    assert "distance_m" in bare and bare["category"] == "Fast food"


async def test_locations_distances_are_coarse_and_places_carry_no_coordinates(world):
    result, pins = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="донер"), "ru", recommend.choose_anchor(ME)
    )
    for place in result["places"]:
        assert "lat" not in place and "lon" not in place
        assert place["distance_m"] % recommend.LOCATION_ROUND_M == 0
    assert "lat" in pins[0]  # the map still gets coordinates (they never go to the model)
    other, _ = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="донер"), "ru", recommend.choose_anchor()
    )
    assert other["anchor"] == "city_centre" and "lat" in other["places"][0]


async def test_accommodation_and_centre_anchors_change_the_order(world):
    near_far = recommend.Anchor(43.3300, 77.0500, recommend.SOURCE_LODGING)  # next to "Далеко"
    result, _ = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="донер"), "ru", near_far
    )
    assert order(result)[0] == "Донер Далеко" and result["anchor"] == "accommodation"


async def test_explicit_near_overrides_the_anchor(world):
    await add_place(world.conn, "Зелёный базар", *GREEN_BAZAAR, "market", "active", 90)
    await add_place(world.conn, "Донер у базара", 76.9545, 43.2615, "cafe_fast_food", "active", 1)
    result, _ = await tools.search_places(
        world.db,
        tools.SearchPlacesArgs(query="донер", near="Зелёный базар"),
        "ru",
        recommend.choose_anchor(ME),
    )
    assert result["anchor"] == "landmark" and "Донер у базара" in order(result)
    assert "Донер Далеко" not in order(result)  # outside the 3 km of the landmark
    missing, _ = await tools.search_places(
        world.db,
        tools.SearchPlacesArgs(query="донер", near="Несуществующая площадь Икс"),
        "ru",
        recommend.choose_anchor(ME),
    )
    assert missing["near_not_found"] is True and missing["anchor"] == "tourist_location"


async def test_category_search_is_ranked_by_the_same_blend(world):
    result, _ = await tools.search_places(
        world.db,
        tools.SearchPlacesArgs(category="cafe_fast_food", limit=3),
        "ru",
        recommend.choose_anchor(ME),
    )
    assert order(result) == ["Донер Знаменитый", "Донер Рядом", "Донер Закрыт"]
    assert all("match" not in p for p in result["places"])


# ------------------------------------------------------------------- the chats (scripted LLM)


def donor_llm():
    return FakeLLM(
        steps=[
            Step(tool_calls=[FakeToolCall("search_places", {"query": "донер"})]),
            Step(text=["Советую Донер Знаменитый."]),
        ]
    )


async def test_guest_chat_donor_question_gets_sorted_places_with_signals(chat_env, conn, caplog):
    await seed(conn)
    llm = donor_llm()
    chat_env.app.state.llm_provider = llm
    body = {
        "messages": [{"role": "user", "content": "где можно отведать вкуснейший донер"}],
        "location": {"lat": ME[0], "lon": ME[1]},
    }
    with caplog.at_level(logging.DEBUG):
        response = await chat_env.client.post(
            "/v1/chat/guest", json=body, headers={"X-Install-Id": INSTALL}
        )
    assert response.status_code == 200, response.text
    tool_result = json.loads(llm.calls[1].messages[-1].content)
    assert [p["name"] for p in tool_result["places"]][:2] == ["Донер Знаменитый", "Донер Рядом"]
    assert tool_result["places"][0]["open_now"] is True
    assert tool_result["anchor"] == "tourist_location"
    # the exact position is nowhere in what the model saw, nor in the logs, nor in the answer
    seen = json.dumps([[m.content for m in c.messages] + [c.system] for c in llm.calls])
    for text in ME_TEXT:
        assert text not in seen and text not in caplog.text and text not in response.text
    pins = [d for n, d in parse_sse(response.text) if n == "map_places"][0]["places"]
    assert pins[0]["name"] == "Донер Знаменитый"


async def test_guest_chat_without_location_uses_the_city_centre(chat_env, conn):
    await seed(conn)
    llm = donor_llm()
    chat_env.app.state.llm_provider = llm
    body = {"messages": [{"role": "user", "content": "донер"}]}
    response = await chat_env.client.post(
        "/v1/chat/guest", json=body, headers={"X-Install-Id": INSTALL}
    )
    assert response.status_code == 200
    assert json.loads(llm.calls[1].messages[-1].content)["anchor"] == "city_centre"


@pytest.mark.parametrize("bad", [{"lat": 91, "lon": 10}, {"lat": 43.2}, {"lat": "x", "lon": 1}])
async def test_a_bad_location_is_a_validation_error(chat_env, bad):
    body = {"messages": [{"role": "user", "content": "донер"}], "location": bad}
    response = await chat_env.client.post("/v1/chat/guest", json=body)
    assert response.status_code == 422


async def tables_with(conn, needle):
    cur = await conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'places'"
    )
    found = []
    for row in await cur.fetchall():
        table = row["tablename"]
        cur = await conn.execute(
            'SELECT count(*) AS n FROM "%s" t WHERE t::text LIKE %%s' % table, ("%" + needle + "%",)
        )
        if (await cur.fetchone())["n"]:
            found.append(table)
    return found


async def test_the_location_is_not_stored_anywhere(chat_env, conn):
    await seed(conn)
    chat_env.app.state.llm_provider = donor_llm()
    body = {
        "messages": [{"role": "user", "content": "донер"}],
        "location": {"lat": ME[0], "lon": ME[1]},
    }
    response = await chat_env.client.post("/v1/chat/guest", json=body)
    assert response.status_code == 200
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers, "ru")
    chat_env.app.state.llm_provider = donor_llm()
    sent = await chat_env.client.post(
        "/v1/chats/%s/messages" % chat["id"],
        headers=headers,
        json={"content": "донер", "location": {"lat": ME[0], "lon": ME[1]}},
    )
    assert sent.status_code == 200
    for needle in ME_TEXT:
        assert await tables_with(conn, needle) == []


async def test_registered_chat_uses_the_location_for_this_turn(chat_env, conn):
    await seed(conn)
    llm = donor_llm()
    chat_env.app.state.llm_provider = llm
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers, "ru")
    response = await chat_env.client.post(
        "/v1/chats/%s/messages" % chat["id"],
        headers=headers,
        json={"content": "где донер", "location": {"lat": ME[0], "lon": ME[1]}},
    )
    assert response.status_code == 200, response.text
    result = json.loads(llm.calls[1].messages[-1].content)
    assert result["anchor"] == "tourist_location"
    assert result["places"][0]["name"] == "Донер Знаменитый"
    seen = json.dumps([[m.content for m in c.messages] for c in llm.calls])
    assert all(text not in seen for text in ME_TEXT)
    assert all(text not in response.text for text in ME_TEXT)
    again = await chat_env.client.post(
        "/v1/chats/%s/messages" % chat["id"], headers=headers, json={"content": "ещё"}
    )
    assert again.status_code == 200
