"""Ш-56: wishes for well-known places outside the v1 area (SSOT §5.4, «до запуска межгорода»)."""

import json
from types import SimpleNamespace

import pytest

from app.analytics import events
from app.db import fetch_all
from app.planner import outside
from app.planner.build import must_have_unmet_json
from app.planner.candidates import select_candidates
from app.providers.llm.fake import Step
from tests.test_chat import call, say, use
from tests.test_live_route import (  # noqa: F401
    CHINESE,
    get_chat,
    live_events,
    settle,
    stored_route,
    world,
)
from tests.test_planner_candidates import brief, fixture_places

# --- matching ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Чарынский каньон", "charyn"),
        ("хочу на Кольсайские озёра", "kolsai"),
        ("Kolsay lakes", "kolsai"),
        ("мавзолей Ходжи Ахмеда Ясави", "yasawi"),  # the mausoleum, not just the city
        ("Yasawi mausoleum in Turkistan", "yasawi"),
        ("съездить в Туркестан", "turkistan"),
        ("озеро Иссык", "issyk_lake"),
        ("Singing Dune", "altyn_emel"),
        ("Kapchagay beach", "konaev"),
        ("Astana", "astana"),
    ],
)
def test_known_places_outside_the_area_are_recognised(text, expected):
    place = outside.outside_wish(text)
    assert place is not None and place.id == expected


@pytest.mark.parametrize(
    "text",
    [
        "Шымбулак",  # inside the v1 area
        "Big Almaty Lake",
        "парк Первого Президента",
        "китайский ресторан",
        "Issyk-Kul",  # Kyrgyzstan, not Issyk lake
        "ресторан Туркестан",  # a venue in Almaty named after the city
        "Turkistan cafe",
        "улица Туркестанская",
        "Hotel Astana",
        "",
        None,
    ],
)
def test_places_inside_the_area_and_venues_are_not_outside(text):
    assert outside.outside_wish(text) is None


def test_catalog_ids_are_unique_and_json_is_localised():
    assert len(outside.BY_ID) == len(outside.PLACES)
    charyn = outside.BY_ID["charyn"]
    assert charyn.as_json("ru") == {
        "id": "charyn", "name": "Чарынский каньон", "region": "Алматинская область",
        "distance_km": charyn.distance_km(),
    }  # fmt: skip
    assert charyn.as_json("en")["name"] == "Charyn Canyon"
    assert 150 <= charyn.distance_km() <= 200  # straight line from the centre of Almaty
    assert outside.BY_ID["yasawi"].distance_km() > 600


def test_analytics_accepts_only_catalog_ids():
    assert "wish_outside_area" in events.SERVER_EVENTS
    assert events.clean_props("wish_outside_area", {"place": "charyn"}) == {"place": "charyn"}
    assert events.clean_props("wish_outside_area", {"place": "my home address"}) == {}
    assert events.clean_props("wish_outside_area", {"place": "charyn", "text": "x"}) == {
        "place": "charyn"
    }


# --- generator -----------------------------------------------------------------------------------


async def test_outside_wish_gets_no_almaty_stand_in_and_is_reported(conn):
    await fixture_places(conn)
    wishes = ["Кольсайские озёра", "Несуществующее место XYZ", "Медеу"]
    sel = await select_candidates(conn, brief(must_haves=wishes))
    assert [m.how for m in sel.must_haves] == ["outside", "none", "name"]
    assert sel.must_haves[0].places == []  # no park or lake in Almaty instead of Kolsai
    plan = SimpleNamespace(selection=sel, layout=SimpleNamespace(must_have_unplaced=[]))
    unmet = must_have_unmet_json(plan, "ru")
    assert unmet[0]["reason"] == "outside_area"
    assert unmet[0]["wish"] == "Кольсайские озёра"
    assert unmet[0]["place_name"] == "Кольсайские озёра"
    assert unmet[0]["outside_area"]["id"] == "kolsai"
    assert unmet[1] == {
        "wish": "Несуществующее место XYZ",
        "place_name": None,
        "reason": "no_place",
    }
    assert len(unmet) == 2


# --- chat: search, brief, live route, analytics -----------------------------------------------


def tool_results(llm):
    """Tool results the model got back, parsed."""
    return [
        json.loads(m.content)
        for c in llm.calls
        for m in c.messages
        if m.role == "tool" and m.content.startswith("{")
    ]


async def run(w, *calls):
    llm = use(w.env, steps=[Step(tool_calls=list(calls)), Step(text=["ok"])])
    before = await stored_route(w.env, w.headers, w.chat["id"])
    response = await say(w.env, w.headers, w.chat["id"])
    return llm, await settle(w.env, w.headers, w.chat["id"], response, before)


async def outside_events(conn):
    return await fetch_all(
        conn,
        "SELECT user_id, install_id, trip_id, place_id, props FROM analytics_events "
        "WHERE name = 'wish_outside_area' ORDER BY id",
    )


async def test_search_says_outside_area_instead_of_nothing_found(world):  # noqa: F811
    llm, _ = await run(world, call("search_places", {"query": "Charyn Canyon"}))
    result = tool_results(llm)[-1]
    assert result["places"] == []
    assert result["outside_area"]["id"] == "charyn"
    assert "nothing found" not in json.dumps(result)


async def test_search_for_a_venue_named_after_a_place_is_a_normal_search(world):  # noqa: F811
    llm, _ = await run(world, call("search_places", {"query": "Turkistan restaurant"}))
    assert "outside_area" not in tool_results(llm)[-1]


async def test_brief_reports_outside_wish_records_demand_once_and_keeps_it(world):  # noqa: F811
    llm, events_ = await run(
        world, call("update_trip_brief", {"must_haves": ["Charyn Canyon", CHINESE]})
    )
    result = tool_results(llm)[-1]
    assert [a["id"] for a in result["outside_area"]] == ["charyn"]
    assert result["outside_area"][0]["wish"] == "Charyn Canyon"
    assert "Charyn Canyon" in result["brief"]["must_haves"]  # the wish stays in the brief
    route = live_events(events_)[-1]
    assert [s["wish"] for s in route["stops"]] == [CHINESE]  # no Almaty stand-in for Charyn
    rows = await outside_events(world.conn)
    assert len(rows) == 1
    assert rows[0]["props"] == {"place": "charyn"}
    assert [rows[0][k] for k in ("user_id", "install_id", "trip_id", "place_id")] == [None] * 4
    # the same wish again (any case) is not counted twice and is not reported again
    llm, _ = await run(world, call("update_trip_brief", {"must_haves": ["charyn canyon"]}))
    assert "outside_area" not in tool_results(llm)[-1]
    assert len(await outside_events(world.conn)) == 1
    assert [s["wish"] for s in (await get_chat(world))["live_route"]["stops"]] == [CHINESE]
