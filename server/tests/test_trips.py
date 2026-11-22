"""Ш-35/Ш-36 end to end: chat (fake LLM) -> build_trip -> trip in the database, route_ready,
rebuild, over-budget variants and the budget choice endpoint."""

import json
import re
from datetime import timedelta

import pytest
from pydantic import SecretStr

from app.chat.brief import today_almaty
from app.config import get_settings
from app.db import fetch_all, fetch_one
from app.providers.llm.fake import Step
from app.routing import FakeRouter
from tests.conftest import parse_sse
from tests.test_chat import call, new_chat, say, sign_in, use
from tests.test_places import add_place, load_categories

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


@pytest.fixture(autouse=True)
def signing_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))


WORLD = [
    # name, lon, lat, category, popularity, entry_kzt, avg_check_kzt, price_per_night_kzt
    ("Музей Кастеева", 76.9535, 43.2570, "museum", 70, 8000, None, None),
    ("Музей инструментов", 76.9390, 43.2570, "museum", 40, 6000, None, None),
    ("Галерея Арт", 76.9500, 43.2480, "gallery", 55, 12000, None, None),
    ("Театр Оперы", 76.9400, 43.2500, "theatre", 65, 15000, None, None),
    ("Парк Горького", 76.9565, 43.2540, "park", 75, 0, None, None),
    ("Кок-Тобе", 76.9747, 43.2330, "viewpoint", 80, 3000, None, None),
    ("Монумент Независимости", 76.9450, 43.2380, "monument", 60, 0, None, None),
    ("Зелёный базар", 76.9560, 43.2610, "market", 50, 0, None, None),
    ("Собор", 76.9540, 43.2590, "religious", 45, 0, None, None),
    ("Набережная", 76.9400, 43.2450, "park", 30, 0, None, None),
    ("Плов-центр", 76.9300, 43.2400, "cafe_oriental", 60, None, 4000, None),
    ("Дастархан", 76.9310, 43.2410, "cafe_kazakh", 50, None, 2500, None),
    ("Бистро", 76.9450, 43.2500, "cafe_european", 40, None, 6000, None),
    ("Хинкальная", 76.9500, 43.2540, "cafe_caucasian", 35, None, 3500, None),
    ("Столовая", 76.9400, 43.2420, "cafe_european", 20, None, 1500, None),
    ("Шашлычная", 76.9460, 43.2460, "cafe_caucasian", 25, None, 2000, None),
    ("Площадь Республики", 76.9455, 43.2389, "landmark", 20, 0, None, None),
    ("Сквер Аллея", 76.9500, 43.2500, "park", 15, 0, None, None),
    ("Фонтаны", 76.9380, 43.2440, "landmark", 12, 0, None, None),
    ("Пекарня-кафе", 76.9420, 43.2440, "cafe_kazakh", 18, None, 1800, None),
    ("Лагман-хаус", 76.9390, 43.2410, "cafe_oriental", 16, None, 1700, None),
    ("Чайхана Дешёвая", 76.9440, 43.2480, "cafe_oriental", 14, None, 1200, None),
    ("Хостел Север", 76.9500, 43.2600, "hostel", 50, None, None, 6000),
    ("Хостел Центр", 76.9460, 43.2400, "hostel", 60, None, None, 8000),
    ("Отель Люкс", 76.9450, 43.2390, "hotel", 70, None, None, 45000),
    ("Отель Без Цены", 76.9400, 43.2300, "hotel", 30, None, None, None),
    ("Гостевой Дом", 76.9300, 43.2200, "guest_house", 20, None, None, 15000),
]


async def seed_world(conn):
    await load_categories(conn)
    await conn.execute(
        "INSERT INTO transport_tariffs "
        "(mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, source)"
        " VALUES ('taxi', '2026-01-01', 500, 0, 150, 'test'), "
        "('scooter', '2026-01-01', 100, 30, 0, 'test'), ('car', '2026-01-01', 0, 0, 40, 'test')"
    )
    for name, lon, lat, cat, pop, entry, check, night in WORLD:
        place_id = await add_place(conn, name, lon, lat, cat, "active", pop)
        await conn.execute(
            "UPDATE places SET entry_price_kzt = %s, avg_check_kzt = %s, "
            "price_per_night_kzt = %s WHERE id = %s",
            (entry, check, night, place_id),
        )


def day(offset):
    return (today_almaty() + timedelta(days=offset)).isoformat()


def brief_call(**fields):
    base = {"start_date": day(10), "end_date": day(12), "budget_kzt": 900000}
    base.update(fields)
    return call("update_trip_brief", base)


async def build(env, headers, chat_id, steps, text="go"):
    """One chat turn that runs `steps`; returns the parsed SSE events."""
    llm = use(env, steps=steps + [Step(text=["Here is your plan."])])
    response = await say(env, headers, chat_id, text)
    assert response.status_code == 200, response.text
    return parse_sse(response.text), llm


async def start(chat_env, conn, **brief):
    await seed_world(conn)
    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    steps = [
        Step(tool_calls=[brief_call(has_accommodation=True, **brief)]),
        Step(tool_calls=[call("build_trip", {})]),
    ]
    events, llm = await build(chat_env, headers, chat["id"], steps)
    return headers, chat, events, llm


def event(events, name):
    found = [data for n, data in events if n == name]
    assert len(found) == 1, [n for n, _ in events]
    return found[0]


async def items(conn, trip_id, variant="main"):
    return await fetch_all(
        conn,
        "SELECT i.*, p.name_ru FROM trip_items i JOIN places p ON p.id = i.place_id "
        "WHERE i.trip_id = %s AND i.variant = %s ORDER BY i.day, i.ord",
        (trip_id, variant),
    )


async def count(conn, table, where="true", params=()):
    row = await fetch_one(conn, "SELECT count(*) AS n FROM %s WHERE %s" % (table, where), params)  # noqa: S608
    return row["n"]


# --- Ш-36: chat -> trip in the database ---------------------------------------------------
async def test_build_trip_writes_the_trip_and_announces_route_ready(chat_env, conn):
    headers, chat, events, llm = await start(chat_env, conn, must_haves=["Плов-центр"])
    assert [n for n, _ in events] == [
        "brief_updated", "map_places", "live_route", "route_ready", "text_delta", "done"
    ]  # fmt: skip
    ready = event(events, "route_ready")
    assert set(ready) == {"trip_id", "version", "days", "warnings", "must_have_unmet", "budget"}
    assert ready["version"] == 1 and ready["days"] == 3
    assert ready["must_have_unmet"] == []
    budget = ready["budget"]
    assert budget["status"] == "ok" and budget["variants"] is None and budget["choice"] is None
    assert budget["budget_kzt"] == 900000 and budget["lodging"]["needed"] is False
    assert budget["lodging"]["options"] == [] and budget["lodging"]["cost_kzt"] == 0
    parts = budget["breakdown"]
    assert parts["lodging_kzt"] == 0 and parts["events_kzt"] == 0
    assert parts["entries_kzt"] > 0 and parts["meals_kzt"] > 0 and parts["transport_kzt"] > 0
    assert budget["total_kzt"] == sum(parts.values())
    assert budget["remaining_kzt"] == 900000 - budget["total_kzt"]

    trip = await fetch_one(conn, "SELECT * FROM trips WHERE chat_id = %s", (chat["id"],))
    assert str(trip["id"]) == ready["trip_id"] and trip["version"] == 1
    assert trip["total_cost_kzt"] == budget["total_kzt"] and trip["budget_kzt"] == 900000
    assert trip["brief"]["must_haves"] == ["Плов-центр"]
    assert trip["brief"]["start_date"] == day(10) and trip["must_have_unmet"] == []
    rows = await items(conn, trip["id"])
    assert rows and {r["variant"] for r in rows} == {"main"}
    assert "Плов-центр" in {r["name_ru"] for r in rows if r["is_must_have"]}
    by_day = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(r)
    assert len(by_day) == 3
    for stops in by_day.values():
        assert [r["ord"] for r in stops] == list(range(1, len(stops) + 1))
        assert all(a["ends_at"] <= b["starts_at"] for a, b in zip(stops, stops[1:]))
        assert sorted(r["meal"] for r in stops if r["kind"] == "meal") == ["dinner", "lunch"]
    legs = await fetch_all(conn, "SELECT * FROM trip_legs WHERE trip_id = %s", (trip["id"],))
    assert len(legs) == len(rows) - len(by_day)  # one leg between consecutive stops
    item_ids = {r["id"] for r in rows}
    for leg in legs:
        assert leg["from_item_id"] in item_ids and leg["to_item_id"] in item_ids
        assert leg["chosen_mode"] in {o["mode"] for o in leg["options"]}
        assert all("steps" not in o and "geometry" in o for o in leg["options"])
    assert sum(r["est_cost_kzt"] for r in rows) + sum(g["cost_kzt"] for g in legs) == (
        budget["total_kzt"]
    )  # fmt: skip

    # the model got a compact day-by-day result and the instruction to explain it
    result = json.loads(llm.calls[-1].messages[-1].content)
    assert result["ok"] and result["trip_id"] == ready["trip_id"] and len(result["days"]) == 3
    first = result["days"][0]["stops"][0]
    assert set(first) >= {"time", "name", "kind", "cost_kzt"}
    assert result["budget"]["status"] == "ok" and "instructions" in result
    assert result["warnings"] == [w["code"] for w in ready["warnings"]]
    audit = await fetch_one(conn, "SELECT tool_calls FROM chat_messages WHERE role = 'assistant'")
    assert [c["name"] for c in audit["tool_calls"]] == ["update_trip_brief", "build_trip"]


async def test_rebuild_updates_the_same_trip_and_increments_the_version(chat_env, conn):
    headers, chat, events, _ = await start(chat_env, conn, must_haves=["Плов-центр"])
    first = event(events, "route_ready")
    before = await items(conn, first["trip_id"])

    again, _ = await build(
        chat_env, headers, chat["id"], [Step(tool_calls=[call("build_trip", {})])]
    )
    second = event(again, "route_ready")
    assert second["trip_id"] == first["trip_id"] and second["version"] == 2
    after = await items(conn, second["trip_id"])
    # nothing changed in the brief: the same plan (determinism), replaced, not duplicated
    key = lambda rows: [(r["day"], r["ord"], r["place_id"], r["starts_at"]) for r in rows]  # noqa: E731
    assert key(after) == key(before)
    assert await count(conn, "trips") == 1

    changed, _ = await build(
        chat_env,
        headers,
        chat["id"],
        [
            Step(tool_calls=[call("update_trip_brief", {"end_date": day(11), "pace": "calm"})]),
            Step(tool_calls=[call("build_trip", {})]),
        ],
    )
    third = event(changed, "route_ready")
    assert third["version"] == 3 and third["days"] == 2
    trip = await fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (third["trip_id"],))
    assert trip["version"] == 3 and trip["end_date"].isoformat() == day(11)
    assert len({r["day"] for r in await items(conn, trip["id"])}) == 2
    assert await count(conn, "trip_items", "trip_id = %s", (trip["id"],)) == len(
        await items(conn, trip["id"])
    )  # the old rows are gone


async def test_a_must_have_without_a_place_is_reported_honestly(chat_env, conn):
    _, chat, events, llm = await start(chat_env, conn, must_haves=["суши-бар Токио"])
    ready = event(events, "route_ready")
    assert ready["must_have_unmet"] == [
        {"wish": "суши-бар Токио", "place_name": None, "reason": "no_place"}
    ]
    trip = await fetch_one(
        conn, "SELECT must_have_unmet FROM trips WHERE chat_id = %s", (chat["id"],)
    )
    assert trip["must_have_unmet"] == ready["must_have_unmet"]  # plan is built anyway
    result = json.loads(llm.calls[-1].messages[-1].content)
    assert result["must_have_unmet"] == ready["must_have_unmet"]
    assert await count(conn, "trip_items") > 0


async def test_without_lodging_options_are_offered_and_their_cost_is_deducted(chat_env, conn):
    await seed_world(conn)
    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    steps = [
        Step(tool_calls=[brief_call(has_accommodation=False)]),
        Step(tool_calls=[call("build_trip", {})]),
    ]
    events, llm = await build(chat_env, headers, chat["id"], steps)
    ready = event(events, "route_ready")
    lodging = ready["budget"]["lodging"]
    assert lodging["needed"] and lodging["nights"] == 2  # 3 days = 2 nights
    options = lodging["options"]
    assert 3 <= len(options) <= 5
    for o in options:
        assert o["total_kzt"] == 2 * o["price_per_night_kzt"]
    assert sum(o["recommended"] for o in options) == 1
    recommended = next(o for o in options if o["recommended"])
    assert (
        lodging["cost_kzt"]
        == recommended["total_kzt"]
        == ready["budget"]["breakdown"]["lodging_kzt"]
    )
    assert any(o["price_assumed"] for o in options)  # the hotel without a price
    codes = [w["code"] for w in ready["warnings"]]
    assert ("lodging_price_assumed" in codes) == recommended["price_assumed"]  # the counted one
    trip_id = ready["trip_id"]
    stored = await fetch_all(
        conn, "SELECT * FROM trip_lodging_options WHERE trip_id = %s ORDER BY rank", (trip_id,)
    )
    assert [str(r["place_id"]) for r in stored] == [o["place_id"] for o in options]
    assert [r["recommended"] for r in stored] == [o["recommended"] for o in options]
    model = json.loads(llm.calls[-1].messages[-1].content)["budget"]["lodging"]
    assert model["options"] and "place_id" not in model["options"][0]


# --- Ш-35: over budget, the two variants and the choice --------------------------------------
async def over_budget_trip(chat_env, conn, cut, **brief):
    """Build with plenty of money, then again with `cut` less than the plan costs."""
    headers, chat, events, _ = await start(chat_env, conn, **brief)
    total = event(events, "route_ready")["budget"]["total_kzt"]
    again, _ = await build(
        chat_env,
        headers,
        chat["id"],
        [
            Step(tool_calls=[call("update_trip_brief", {"budget_kzt": total - cut})]),
            Step(tool_calls=[call("build_trip", {})]),
        ],
    )
    return headers, chat, event(again, "route_ready"), total


async def test_over_budget_warns_and_stores_both_variants_next_to_the_plan(chat_env, conn):
    headers, chat, ready, total = await over_budget_trip(
        chat_env, conn, 9000, must_haves=["Музей Кастеева"]
    )
    budget = ready["budget"]
    assert budget["status"] == "over" and budget["shortfall_kzt"] == 9000
    assert budget["total_kzt"] == total and budget["remaining_kzt"] == -9000
    assert "over_budget" in [w["code"] for w in ready["warnings"]]
    assert budget["must_haves_exceed_budget"] is False
    drop, cheaper = budget["variants"]["drop_places"], budget["variants"]["cheaper"]
    assert drop["feasible"] and cheaper["feasible"]
    assert (
        drop["total_kzt"] <= budget["budget_kzt"] and cheaper["total_kzt"] <= budget["budget_kzt"]
    )
    assert drop["removed"] and all(set(r) == {"place_id", "name"} for r in drop["removed"])
    assert "Музей Кастеева" not in {r["name"] for r in drop["removed"]}  # the must-have stays
    assert cheaper["swaps"] and "Музей Кастеева" not in {
        s["from"]["name"] for s in cheaper["swaps"]
    }  # fmt: skip
    trip_id = ready["trip_id"]
    for variant in ("main", "drop_places", "cheaper"):
        rows = await items(conn, trip_id, variant)
        assert "Музей Кастеева" in {r["name_ru"] for r in rows}  # must-have in every variant
    legs = await fetch_all(
        conn,
        "SELECT l.variant AS lv, i.variant AS iv FROM trip_legs l JOIN trip_items i "
        "ON i.id = l.to_item_id WHERE l.trip_id = %s",
        (trip_id,),
    )
    assert legs and all(r["lv"] == r["iv"] for r in legs)
    stored = (await fetch_one(conn, "SELECT budget FROM trips WHERE id = %s", (trip_id,)))["budget"]
    assert not UUID_RE.search(json.dumps(stored))  # no place ids in the stored summary
    assert stored["variants"]["drop_places"]["removed_count"] == len(drop["removed"])


async def pick(env, headers, trip_id, choice):
    return await env.client.post(
        "/v1/trips/%s/budget-choice" % trip_id, headers=headers, json={"choice": choice}
    )


@pytest.mark.parametrize("choice", ["drop_places", "cheaper"])
async def test_choosing_a_variant_makes_it_the_plan(chat_env, conn, choice):
    headers, chat, ready, _ = await over_budget_trip(
        chat_env, conn, 9000, must_haves=["Музей Кастеева"]
    )
    trip_id = ready["trip_id"]
    expected = await items(conn, trip_id, choice)
    variant = ready["budget"]["variants"][choice]

    response = await pick(chat_env, headers, trip_id, choice)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trip_id"] == trip_id and body["version"] == ready["version"] + 1
    assert body["budget"]["choice"] == choice and body["budget"]["variants"] is None
    assert body["budget"]["status"] == "ok"
    assert body["budget"]["total_kzt"] == variant["total_kzt"]
    assert body["budget"]["breakdown"] == variant["breakdown"]

    assert {r["variant"] for r in await fetch_all(conn, "SELECT variant FROM trip_items")} == {
        "main"
    }
    now = await items(conn, trip_id)
    key = lambda rows: [(r["day"], r["ord"], r["place_id"], r["starts_at"]) for r in rows]  # noqa: E731
    assert key(now) == key(expected)
    legs = await fetch_all(conn, "SELECT variant, to_item_id FROM trip_legs")
    assert {g["variant"] for g in legs} == {"main"}  # fmt: skip
    assert {g["to_item_id"] for g in legs} <= {r["id"] for r in now}
    trip = await fetch_one(conn, "SELECT * FROM trips WHERE id = %s", (trip_id,))
    assert trip["version"] == body["version"] and trip["budget_choice"] == choice
    assert trip["total_cost_kzt"] == variant["total_kzt"]
    assert "over_budget" not in [w["code"] for w in trip["warnings"]]
    assert (
        sum(r["est_cost_kzt"] for r in now)
        + (await fetch_one(conn, "SELECT sum(cost_kzt) AS s FROM trip_legs"))["s"]
        == variant["total_kzt"]
    )

    again = await pick(chat_env, headers, trip_id, choice)
    assert again.status_code == 409 and again.json()["error"]["code"] == "budget_choice_unavailable"


async def test_keep_accepts_the_plan_over_budget(chat_env, conn):
    headers, _, ready, total = await over_budget_trip(chat_env, conn, 9000)
    before = await items(conn, ready["trip_id"])
    response = await pick(chat_env, headers, ready["trip_id"], "keep")
    assert response.status_code == 200
    budget = response.json()["budget"]
    assert budget["choice"] == "keep" and budget["status"] == "over"
    assert budget["total_kzt"] == total and budget["shortfall_kzt"] == 9000
    after = await items(conn, ready["trip_id"])
    assert [r["place_id"] for r in after] == [r["place_id"] for r in before]
    assert await count(conn, "trip_items", "variant <> 'main'") == 0
    trip = await fetch_one(conn, "SELECT warnings FROM trips WHERE id = %s", (ready["trip_id"],))
    assert "over_budget" in [w["code"] for w in trip["warnings"]]  # still true


async def test_cheaper_variant_switches_the_recommended_lodging(chat_env, conn):
    await seed_world(conn)
    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    base = [
        Step(tool_calls=[brief_call(has_accommodation=False)]),
        Step(tool_calls=[call("build_trip", {})]),
    ]
    events, _ = await build(chat_env, headers, chat["id"], base)
    ready = event(events, "route_ready")
    options = ready["budget"]["lodging"]["options"]
    cheapest = min(options, key=lambda o: o["total_kzt"])
    recommended = next(o for o in options if o["recommended"])
    over = ready["budget"]["total_kzt"] - 3000
    events, _ = await build(
        chat_env, headers, chat["id"],
        [Step(tool_calls=[call("update_trip_brief", {"budget_kzt": over})]),
         Step(tool_calls=[call("build_trip", {})])],
    )  # fmt: skip
    ready = event(events, "route_ready")
    variant = ready["budget"]["variants"]["cheaper"]
    assert cheapest["place_id"] != recommended["place_id"]  # the fixture makes them differ
    assert variant["lodging"]["place_id"] == cheapest["place_id"]
    assert variant["lodging_total_kzt"] == cheapest["total_kzt"]
    body = (await pick(chat_env, headers, ready["trip_id"], "cheaper")).json()
    assert body["budget"]["lodging"]["cost_kzt"] == cheapest["total_kzt"]
    rows = await fetch_all(
        conn, "SELECT place_id::text AS p, recommended FROM trip_lodging_options"
    )
    assert [r["p"] for r in rows if r["recommended"]] == [cheapest["place_id"]]


async def test_must_haves_that_exceed_the_budget_are_never_dropped_and_the_user_is_told(
    chat_env, conn
):
    headers, chat, events, _ = await start(
        chat_env, conn, must_haves=["Театр Оперы", "Галерея Арт", "Плов-центр"], budget_kzt=20000
    )
    ready = event(events, "route_ready")
    budget = ready["budget"]
    assert budget["status"] == "over" and budget["must_haves_exceed_budget"] is True
    assert budget["must_have_cost_kzt"] >= 15000 + 12000 + 4000 > budget["budget_kzt"]
    assert "must_haves_exceed_budget" in [w["code"] for w in ready["warnings"]]
    for kind, variant in budget["variants"].items():
        assert variant["feasible"] is False
        rows = await items(conn, ready["trip_id"], kind)
        names = {r["name_ru"] for r in rows if r["is_must_have"]}
        assert {"Театр Оперы", "Галерея Арт"} <= names, kind
    main = await items(conn, ready["trip_id"])
    assert {"Театр Оперы", "Галерея Арт", "Плов-центр"} <= {r["name_ru"] for r in main}


async def test_budget_choice_access_and_validation(chat_env, conn):
    headers, _, ready, _ = await over_budget_trip(chat_env, conn, 9000)
    trip_id = ready["trip_id"]
    c = chat_env.client
    url = "/v1/trips/%s/budget-choice" % trip_id
    assert (await c.post(url, json={"choice": "keep"})).status_code == 401
    assert (
        await c.post(url, headers={"Authorization": "Bearer nope"}, json={"choice": "keep"})
    ).status_code == 401
    assert (await c.post(url, headers=headers, json={"choice": "cheapest"})).status_code == 422
    assert (await c.post(url, headers=headers, json={})).status_code == 422
    other = await sign_in(conn, "other@example.com")
    assert (await pick(chat_env, other, trip_id, "keep")).status_code == 404  # not theirs
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await pick(chat_env, headers, missing, "keep")).status_code == 404
    assert await count(conn, "trip_items", "variant <> 'main'") > 0  # nothing was touched
    assert (await pick(chat_env, headers, trip_id, "keep")).status_code == 200


async def test_no_choice_when_the_plan_fits(chat_env, conn):
    headers, _, events, _ = await start(chat_env, conn)
    ready = event(events, "route_ready")
    response = await pick(chat_env, headers, ready["trip_id"], "keep")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "budget_choice_unavailable"


async def test_an_incomplete_brief_builds_nothing(chat_env, conn):
    await seed_world(conn)
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    events, llm = await build(
        chat_env, headers, chat["id"], [Step(tool_calls=[call("build_trip", {})])]
    )
    assert "route_ready" not in [n for n, _ in events]
    result = json.loads(llm.calls[1].messages[-1].content)
    assert result["ok"] is False and "incomplete" in result["error"]
    assert await count(conn, "trips") == 0


async def test_valhalla_down_still_gives_a_plan_with_estimated_legs(chat_env, conn):
    from app.routing import RoutingUnavailable

    class Down(FakeRouter):
        async def route(self, *a, **k):
            raise RoutingUnavailable("down")

        async def matrix(self, *a, **k):
            raise RoutingUnavailable("down")

    await seed_world(conn)
    chat_env.app.state.routing_provider = Down()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    events, _ = await build(
        chat_env,
        headers,
        chat["id"],
        [
            Step(tool_calls=[brief_call(has_accommodation=True)]),
            Step(tool_calls=[call("build_trip", {})]),
        ],
    )
    ready = event(events, "route_ready")
    assert "travel_estimated" in [w["code"] for w in ready["warnings"]]
    legs = await fetch_all(conn, "SELECT estimated, options, chosen_mode FROM trip_legs")
    assert legs and all(
        g["estimated"] and g["options"] == [] and g["chosen_mode"] is None for g in legs
    )
    assert ready["budget"]["breakdown"]["transport_kzt"] == 0
