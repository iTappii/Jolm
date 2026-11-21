"""Ш-38: removing / replacing stops through the API and the chat tools, memory signals."""

import json

from app.db import fetch_all, fetch_one
from app.providers.llm.fake import Step
from tests.test_chat import call
from tests.test_trips import build, count, event, over_budget_trip, start
from tests.test_trips_read import get


async def plan(env, headers, trip_id):
    return (await get(env, headers, trip_id)).json()


def all_items(trip):
    return [i for d in trip["days"] for i in d["items"]]


def day_of(trip, item_id):
    return next(d for d in trip["days"] if any(i["id"] == item_id for i in d["items"]))


def pick(trip, kind="activity", must=False, min_items=3):
    """An item of a day with at least `min_items` stops."""
    for d in trip["days"]:
        if len(d["items"]) < min_items:
            continue
        for i in d["items"]:
            if i["kind"] == kind and i["must_have"] == must:
                return d, i
    raise AssertionError("no such item")


async def post(env, headers, trip_id, item_id, action, body=None, lang=None):
    h = dict(headers, **({"Accept-Language": lang} if lang else {}))
    return await env.client.post(
        "/v1/trips/%s/items/%s/%s" % (trip_id, item_id, action), headers=h, json=body
    )


def assert_day_is_consistent(day):
    items = day["items"]
    assert [i["ord"] for i in items] == list(range(1, len(items) + 1))
    assert all(a["ends_at"] <= b["starts_at"] for a, b in zip(items, items[1:]))
    assert [leg["to_item_id"] for leg in day["legs"]] == [i["id"] for i in items[1:]]
    for leg in day["legs"]:
        assert leg["chosen_mode"] in {o["mode"] for o in leg["options"]}


async def check_totals(conn, trip):
    """The stored budget equals the rows of the plan (same rule as the planner's costs)."""
    row = await fetch_one(
        conn, "SELECT total_cost_kzt, budget FROM trips WHERE id = %s", (trip["id"],)
    )
    items = await fetch_all(
        conn,
        "SELECT est_cost_kzt FROM trip_items WHERE trip_id = %s AND variant = 'main'",
        (trip["id"],),
    )
    legs = await fetch_all(
        conn,
        "SELECT cost_kzt FROM trip_legs WHERE trip_id = %s AND variant = 'main'",
        (trip["id"],),
    )
    total = sum(r["est_cost_kzt"] for r in items) + sum(r["cost_kzt"] for r in legs)
    assert row["total_cost_kzt"] == row["budget"]["total_kzt"] == total
    parts = row["budget"]["breakdown"]
    assert sum(parts.values()) == total
    assert row["budget"]["remaining_kzt"] == row["budget"]["budget_kzt"] - total


# --- remove -----------------------------------------------------------------------------
async def test_remove_retimes_only_that_day_and_writes_a_memory_signal(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    before = await plan(chat_env, headers, ready["trip_id"])
    day, item = pick(before)
    others_before = {d["date"]: d for d in before["days"] if d["date"] != day["date"]}

    response = await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "trip_id", "version", "action", "changed_days", "budget", "removed", "dropped",
    }  # fmt: skip
    assert body["version"] == 2 and body["action"] == "remove"
    assert body["changed_days"] == [day["date"]]
    assert body["removed"] == {
        "item_id": item["id"],
        "place": {
            "id": item["place"]["id"],
            "name": item["place"]["name"],
            "name_lang": item["place"]["name_lang"],
            "category": item["place"]["category"],
            "lat": item["place"]["lat"],
            "lon": item["place"]["lon"],
        },
    }
    assert body["dropped"] == []
    assert set(body["budget"]) == {
        "status",
        "total_kzt",
        "remaining_kzt",
        "shortfall_kzt",
        "breakdown",
    }

    after = await plan(chat_env, headers, ready["trip_id"])
    assert after["version"] == 2 and after["total_cost_kzt"] == body["budget"]["total_kzt"]
    new_day = day_of(after, next(i["id"] for i in day["items"] if i["id"] != item["id"]))
    assert len(new_day["items"]) == len(day["items"]) - 1
    assert item["id"] not in {i["id"] for i in new_day["items"]}
    assert_day_is_consistent(new_day)
    # the other days are untouched: same ids, times and legs
    for d in after["days"]:
        if d["date"] != day["date"]:
            assert d == others_before[d["date"]]
    # the stops that stayed keep their item ids
    assert {i["id"] for i in new_day["items"]} == {i["id"] for i in day["items"]} - {item["id"]}
    await check_totals(conn, {"id": ready["trip_id"]})

    signal = await fetch_one(conn, "SELECT * FROM user_place_signals")
    assert str(signal["place_id"]) == item["place"]["id"] and signal["signal"] == "removed"
    assert signal["category_slug"] == item["place"]["category"]
    assert str(signal["trip_id"]) == ready["trip_id"]
    assert await count(conn, "user_place_signals") == 1


async def built(chat_env, conn, **brief):
    headers, chat, events, _ = await start(chat_env, conn, **brief)
    return headers, chat, event(events, "route_ready")


async def test_an_edit_recounts_the_hours_assumed_warning(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip_id = ready["trip_id"]
    before = await plan(chat_env, headers, trip_id)
    day, item = pick(before)
    # the stored warning is stale on purpose: an edit must replace it with the real count
    await conn.execute(
        "UPDATE trips SET warnings = warnings || %s::jsonb",
        ['[{"code": "hours_assumed", "date": null, "detail": "999"}]'],
    )
    assert (await post(chat_env, headers, trip_id, item["id"], "remove")).status_code == 200
    expected = (
        await fetch_one(
            conn,
            "SELECT count(DISTINCT place_id) AS n FROM trip_items "
            "WHERE trip_id = %s AND variant = 'main' AND hours_assumed",
            (trip_id,),
        )
    )["n"]
    row = await fetch_one(conn, "SELECT warnings FROM trips WHERE id = %s", (trip_id,))
    found = [w for w in row["warnings"] if w["code"] == "hours_assumed"]
    if expected:
        assert [w["detail"] for w in found] == [str(expected)]
    else:
        assert found == []


async def test_remove_twice_or_a_foreign_item_is_404_and_changes_nothing(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = await plan(chat_env, headers, ready["trip_id"])
    _, item = pick(trip)
    assert (
        await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    ).status_code == 200
    again = await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    assert again.status_code == 404 and again.json()["error"]["code"] == "not_found"
    unknown = await post(chat_env, headers, ready["trip_id"], ready["trip_id"], "remove")
    assert unknown.status_code == 404
    assert (await plan(chat_env, headers, ready["trip_id"]))["version"] == 2
    assert await count(conn, "user_place_signals") == 1


async def test_a_must_have_needs_force(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn, must_haves=["Музей Кастеева"])
    trip = await plan(chat_env, headers, ready["trip_id"])
    day, item = next(
        (d, i) for d in trip["days"] for i in d["items"] if i["must_have"]
    )  # the must-have
    refused = await post(chat_env, headers, ready["trip_id"], item["id"], "remove", lang="ru")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "must_have"
    assert "обязательн" in refused.json()["error"]["message"]
    assert (await plan(chat_env, headers, ready["trip_id"]))["version"] == 1
    assert await count(conn, "user_place_signals") == 0
    plain = await post(chat_env, headers, ready["trip_id"], item["id"], "remove", {"force": False})
    assert plain.status_code == 409

    forced = await post(chat_env, headers, ready["trip_id"], item["id"], "remove", {"force": True})
    assert forced.status_code == 200, forced.text
    after = await plan(chat_env, headers, ready["trip_id"])
    assert item["id"] not in {i["id"] for i in all_items(after)}
    assert after["must_have_unmet"] == [
        {"wish": None, "place_name": "Музей Кастеева", "reason": "removed_by_user"}
    ]
    assert await count(conn, "user_place_signals") == 1


async def test_removing_a_meal_and_the_last_stop_of_a_day(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = await plan(chat_env, headers, ready["trip_id"])
    day, lunch = next((d, i) for d in trip["days"] for i in d["items"] if i["meal"] == "lunch")
    ok = await post(chat_env, headers, ready["trip_id"], lunch["id"], "remove")
    assert ok.status_code == 200
    # empty a whole day, one stop after another
    after = await plan(chat_env, headers, ready["trip_id"])
    target = next(d for d in after["days"] if d["date"] == day["date"])
    for i in list(target["items"]):
        response = await post(chat_env, headers, ready["trip_id"], i["id"], "remove")
        assert response.status_code == 200, response.text
    final = await plan(chat_env, headers, ready["trip_id"])
    empty = next(d for d in final["days"] if d["date"] == day["date"])
    assert empty == {"date": day["date"], "items": [], "legs": []}
    assert final["version"] == 2 + len(target["items"])
    await check_totals(conn, {"id": ready["trip_id"]})


async def test_a_transport_choice_survives_an_edit_of_the_same_day(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = await plan(chat_env, headers, ready["trip_id"])
    day = next(d for d in trip["days"] if len(d["items"]) >= 4)
    leg = next(x for x in day["legs"] if len(x["options"]) > 1)
    other = next(o["mode"] for o in leg["options"] if o["mode"] != leg["chosen_mode"])
    chosen = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], leg["id"]),
        headers=headers,
        json={"mode": other},
    )
    assert chosen.status_code == 200
    items = {i["id"]: i for i in day["items"]}
    from_place = items[leg["from_item_id"]]["place"]["id"]
    to_place = items[leg["to_item_id"]]["place"]["id"]
    # remove a stop that is not part of that transition
    victim = next(
        i for i in day["items"]
        if i["place"]["id"] not in (from_place, to_place) and not i["must_have"]
    )  # fmt: skip
    assert (
        await post(chat_env, headers, ready["trip_id"], victim["id"], "remove")
    ).status_code == 200
    after = await plan(chat_env, headers, ready["trip_id"])
    new_day = next(d for d in after["days"] if d["date"] == day["date"])
    by_id = {i["id"]: i["place"]["id"] for i in new_day["items"]}
    same = [
        x for x in new_day["legs"]
        if by_id.get(x["from_item_id"]) == from_place and by_id.get(x["to_item_id"]) == to_place
    ]  # fmt: skip
    assert same and same[0]["chosen_mode"] == other  # the pair is still a transition


async def test_editing_drops_the_stale_budget_variants(chat_env, conn):
    headers, chat, ready, total = await over_budget_trip(
        chat_env, conn, 9000, must_haves=["Музей Кастеева"]
    )
    trip = await plan(chat_env, headers, ready["trip_id"])
    assert trip["budget"]["variants"] is not None
    day, item = pick(trip, min_items=1)
    response = await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    assert response.status_code == 200, response.text
    after = await plan(chat_env, headers, ready["trip_id"])
    assert after["budget"]["variants"] is None
    assert (
        await count(conn, "trip_items", "trip_id = %s AND variant <> 'main'", (ready["trip_id"],))
        == 0
    )
    assert after["budget"]["status"] == response.json()["budget"]["status"]
    choice = await chat_env.client.post(
        "/v1/trips/%s/budget-choice" % ready["trip_id"], headers=headers, json={"choice": "keep"}
    )
    assert choice.status_code == 409  # nothing to choose any more
    codes = [w["code"] for w in after["warnings"]]
    assert ("over_budget" in codes) == (after["budget"]["status"] == "over")
    await check_totals(conn, {"id": ready["trip_id"]})


# --- replace ----------------------------------------------------------------------------
async def test_replace_by_category_keeps_the_slot_and_signals(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = await plan(chat_env, headers, ready["trip_id"])
    taken = {i["place"]["id"] for i in all_items(trip)}
    await conn.execute(  # a free, popular park next to the centre: the best candidate
        "INSERT INTO places (name_ru, name_en, geom, status, category_id, popularity) "
        "SELECT 'Свободный парк', 'Free Park', ST_GeogFromText('POINT(76.95 43.25)'), "
        "'active', id, 100 FROM place_categories WHERE slug = 'park'"
    )
    day, item = pick(trip, min_items=3)
    index = next(n for n, i in enumerate(day["items"]) if i["id"] == item["id"])

    response = await post(
        chat_env, headers, ready["trip_id"], item["id"], "replace", {"category": "park"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "trip_id", "version", "action", "changed_days", "budget", "replaced", "replacement",
        "dropped",
    }  # fmt: skip
    assert body["action"] == "replace" and body["version"] == 2 and body["dropped"] == []
    assert body["replaced"]["item_id"] == item["id"]
    new = body["replacement"]
    assert new["place"]["category"] == "park" and new["place"]["id"] not in taken
    assert new["item_id"] != item["id"] and set(new["place"]) == {
        "id", "name", "category", "lat", "lon",
    }  # fmt: skip

    after = await plan(chat_env, headers, ready["trip_id"])
    new_day = next(d for d in after["days"] if d["date"] == day["date"])
    assert len(new_day["items"]) == len(day["items"])
    assert new_day["items"][index]["id"] == new["item_id"]
    assert new_day["items"][index]["place"]["id"] == new["place"]["id"]
    assert_day_is_consistent(new_day)
    for d in after["days"]:
        if d["date"] != day["date"]:
            assert d == next(x for x in trip["days"] if x["date"] == d["date"])
    signal = await fetch_one(conn, "SELECT * FROM user_place_signals")
    assert signal["signal"] == "replaced" and str(signal["place_id"]) == item["place"]["id"]
    await check_totals(conn, {"id": ready["trip_id"]})


async def test_replace_by_place_id_and_by_name(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = await plan(chat_env, headers, ready["trip_id"])
    taken = [i["place"]["id"] for i in all_items(trip)]
    spare = await fetch_one(
        conn,
        "SELECT id, name_ru FROM places WHERE status = 'active' AND kind <> 'accommodation' "
        "AND id <> ALL(%s::uuid[]) AND name_ru = 'Фонтаны'",
        (taken,),
    )
    day, item = pick(trip, min_items=3)
    if spare is not None:
        by_id = await post(
            chat_env,
            headers,
            ready["trip_id"],
            item["id"],
            "replace",
            {"place_id": str(spare["id"])},
        )
        assert by_id.status_code == 200, by_id.text
        assert by_id.json()["replacement"]["place"]["id"] == str(spare["id"])
        item = next(  # the new item
            i for i in all_items(await plan(chat_env, headers, ready["trip_id"]))
            if i["place"]["id"] == str(spare["id"])
        )  # fmt: skip
    await conn.execute(
        "INSERT INTO places (name_ru, geom, status, category_id, popularity) "
        "SELECT 'Уникальный Сад', ST_GeogFromText('POINT(76.95 43.25)'), 'active', id, 50 "
        "FROM place_categories WHERE slug = 'park'"
    )
    by_name = await post(
        chat_env, headers, ready["trip_id"], item["id"], "replace", {"query": "Уникальный"}
    )
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["replacement"]["place"]["name"] == "Уникальный Сад"


async def test_replace_refusals(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn, must_haves=["Музей Кастеева"])
    trip = await plan(chat_env, headers, ready["trip_id"])
    _, item = pick(trip, min_items=3)
    _, lunch = next((d, i) for d in trip["days"] for i in d["items"] if i["meal"] == "lunch")
    hostel = (await fetch_one(conn, "SELECT id FROM places WHERE name_ru = 'Хостел Центр'"))["id"]
    url = (chat_env, headers, ready["trip_id"])

    for body in ({}, {"category": "park", "query": "Парк"}, {"query": "x"}):
        response = await post(*url, item["id"], "replace", body)
        assert response.status_code == 422, body
    # accommodation is not a replacement
    nope = await post(*url, item["id"], "replace", {"place_id": str(hostel)})
    assert nope.status_code == 409 and nope.json()["error"]["code"] == "no_replacement"
    # nothing matches
    nothing = await post(*url, item["id"], "replace", {"query": "несуществующее заведение"})
    assert nothing.status_code == 409 and nothing.json()["error"]["code"] == "no_replacement"
    # a meal slot takes only a food place (a park is not a lunch)
    park = await post(*url, lunch["id"], "replace", {"category": "park"})
    assert park.status_code == 409 and park.json()["error"]["code"] == "no_replacement"
    # a place that is already in the trip is no replacement
    used = next(i for i in all_items(trip) if i["id"] != item["id"] and not i["must_have"])
    again = await post(*url, item["id"], "replace", {"place_id": used["place"]["id"]})
    assert again.status_code == 409
    must = next(i for i in all_items(trip) if i["must_have"])
    guarded = await post(*url, must["id"], "replace", {"category": "park"})
    assert guarded.status_code == 409 and guarded.json()["error"]["code"] == "must_have"
    assert (await plan(chat_env, headers, ready["trip_id"]))["version"] == 1
    assert await count(conn, "user_place_signals") == 0
    await conn.execute(
        "INSERT INTO places (name_ru, geom, status, category_id, popularity) "
        "SELECT 'Свободный парк', ST_GeogFromText('POINT(76.95 43.25)'), 'active', id, 100 "
        "FROM place_categories WHERE slug = 'park'"
    )
    forced = await post(*url, must["id"], "replace", {"category": "park", "force": True})
    assert forced.status_code == 200, forced.text
    after = await plan(chat_env, headers, ready["trip_id"])
    assert after["must_have_unmet"][0]["reason"] == "replaced_by_user"


async def test_replace_a_meal_with_another_meal(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = await plan(chat_env, headers, ready["trip_id"])
    day, dinner = next((d, i) for d in trip["days"] for i in d["items"] if i["meal"] == "dinner")
    response = await post(
        chat_env, headers, ready["trip_id"], dinner["id"], "replace", {"category": "cafe_oriental"}
    )
    assert response.status_code in (200, 409), response.text
    if response.status_code == 200:
        item = response.json()["replacement"]
        after = await plan(chat_env, headers, ready["trip_id"])
        row = next(i for i in all_items(after) if i["id"] == item["item_id"])
        assert row["kind"] == "meal" and row["meal"] == "dinner"


# --- chat tools -------------------------------------------------------------------------
async def test_chat_edits_the_plan_through_tools_and_announces_trip_updated(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn, must_haves=["Музей Кастеева"])
    trip = await plan(chat_env, headers, ready["trip_id"])
    day, item = pick(trip, min_items=3)
    plain_second = next(
        i for d in trip["days"] for i in d["items"]
        if i["kind"] == "activity" and not i["must_have"] and i["id"] != item["id"]
    )  # fmt: skip

    events, llm = await build(
        chat_env,
        headers,
        chat["id"],
        [
            Step(tool_calls=[call("get_trip_plan", {})]),
            Step(tool_calls=[call("remove_trip_item", {"item_id": item["id"]})]),
            Step(tool_calls=[call("replace_trip_item", {
                "item_id": plain_second["id"], "category": "park"})]),
        ],
        text="remove the first and swap the second for a park",
    )  # fmt: skip
    names = [n for n, _ in events]
    assert names.count("trip_updated") == 2 and "route_ready" not in names
    first, second = [d for n, d in events if n == "trip_updated"]
    assert set(first) == {"trip_id", "version", "action", "changed_days", "budget"}
    assert set(first["budget"]) == {"status", "total_kzt", "remaining_kzt"}
    assert first["trip_id"] == ready["trip_id"] and first["version"] == 2
    assert first["action"] == "remove" and first["changed_days"] == [day["date"]]
    assert second["version"] == 3 and second["action"] == "replace"

    results = [json.loads(m.content) for m in llm.calls[-1].messages if m.role == "tool"]
    plan_result, removed, replaced = results
    assert plan_result["ok"] and plan_result["version"] == 1
    ids = {s["item_id"] for d in plan_result["days"] for s in d["stops"]}
    assert item["id"] in ids and plain_second["id"] in ids
    assert removed["ok"] and removed["version"] == 2 and removed["changed_days"] == [day["date"]]
    assert removed["days"][0]["stops"] and all("item_id" in s for s in removed["days"][0]["stops"])
    assert replaced["ok"] and replaced["replacement"]["place"]["category"] == "park"
    after = await plan(chat_env, headers, ready["trip_id"])
    assert after["version"] == 3
    assert await count(conn, "user_place_signals") == 2
    audit = await fetch_one(conn, "SELECT tool_calls FROM chat_messages WHERE role = 'assistant' "
                                  "ORDER BY id DESC LIMIT 1")  # fmt: skip
    assert [c["name"] for c in audit["tool_calls"]] == [
        "get_trip_plan", "remove_trip_item", "replace_trip_item",
    ]  # fmt: skip


async def test_chat_must_have_needs_confirmation_then_force(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn, must_haves=["Музей Кастеева"])
    trip = await plan(chat_env, headers, ready["trip_id"])
    must = next(i for i in all_items(trip) if i["must_have"])
    events, llm = await build(
        chat_env,
        headers,
        chat["id"],
        [Step(tool_calls=[call("remove_trip_item", {"item_id": must["id"]})])],
    )
    assert "trip_updated" not in [n for n, _ in events]
    refusal = json.loads(llm.calls[-1].messages[-1].content)
    assert (
        refusal["ok"] is False
        and refusal["error"] == "must_have"
        and "force=true" in refusal["hint"]
    )
    assert (await plan(chat_env, headers, ready["trip_id"]))["version"] == 1

    events, llm = await build(
        chat_env,
        headers,
        chat["id"],
        [Step(tool_calls=[call("remove_trip_item", {"item_id": must["id"], "force": True})])],
    )
    assert [d for n, d in events if n == "trip_updated"][0]["version"] == 2


async def test_chat_tools_without_a_trip_or_with_bad_ids_report_errors(chat_env, conn):
    from app.routing import FakeRouter
    from tests.test_chat import new_chat, sign_in
    from tests.test_trips import seed_world

    await seed_world(conn)
    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    _, llm = await build(
        chat_env,
        headers,
        chat["id"],
        [
            Step(tool_calls=[call("get_trip_plan", {})]),
            Step(tool_calls=[call("remove_trip_item", {"item_id": "not-a-uuid"})]),
        ],
    )
    first, second = [json.loads(m.content) for m in llm.calls[-1].messages if m.role == "tool"]
    assert first["ok"] is False and "build_trip" in first["error"]
    assert second["ok"] is False and "invalid arguments" in second["error"]


async def test_build_trip_result_carries_item_ids(chat_env, conn):
    headers, chat, events, llm = await start(chat_env, conn)
    result = json.loads(
        next(
            m.content for m in llm.calls[-1].messages if m.role == "tool" and "trip_id" in m.content
        )
    )
    stops = [s for d in result["days"] for s in d["stops"]]
    stored = {str(r["id"]) for r in await fetch_all(conn, "SELECT id FROM trip_items")}
    assert stops and {s["item_id"] for s in stops} == stored
