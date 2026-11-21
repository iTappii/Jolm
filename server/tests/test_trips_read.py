"""Ш-37 (server): GET /v1/trips, GET /v1/trips/{id}, POST /v1/trips/{id}/legs/{leg_id}/mode."""

import json

from app.db import fetch_all, fetch_one
from app.providers.llm.fake import Step
from tests.test_chat import call, sign_in
from tests.test_trips import (
    UUID_RE,
    build,
    day,
    event,
    over_budget_trip,
    seed_world,
    start,
)


async def built(chat_env, conn, **brief):
    headers, chat, events, _ = await start(chat_env, conn, **brief)
    return headers, chat, event(events, "route_ready")


async def get(env, headers, trip_id, lang=None):
    h = dict(headers, **({"Accept-Language": lang} if lang else {}))
    return await env.client.get("/v1/trips/%s" % trip_id, headers=h)


async def test_endpoints_require_auth_and_hide_foreign_trips(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    c = chat_env.client
    leg = (await fetch_one(conn, "SELECT id FROM trip_legs LIMIT 1"))["id"]
    item = (await fetch_one(conn, "SELECT id FROM trip_items LIMIT 1"))["id"]
    tid = ready["trip_id"]
    urls = [
        ("GET", "/v1/trips", None),
        ("GET", "/v1/trips/%s" % tid, None),
        ("POST", "/v1/trips/%s/legs/%s/mode" % (tid, leg), {"mode": "walk"}),
        ("POST", "/v1/trips/%s/items/%s/remove" % (tid, item), None),
        ("POST", "/v1/trips/%s/items/%s/replace" % (tid, item), {"query": "Парк"}),
    ]
    for method, url, body in urls:
        response = await c.request(method, url, json=body)
        assert response.status_code == 401, url
    other = await sign_in(conn, "b@example.com")
    assert (await c.get("/v1/trips", headers=other)).json() == {"items": []}
    for method, url, body in urls[1:]:
        response = await c.request(method, url, headers=other, json=body)
        assert response.status_code == 404, url
        assert response.json()["error"]["code"] == "not_found"


async def test_list_trips_has_the_summary_of_each_trip(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    response = await chat_env.client.get("/v1/trips", headers=headers)
    assert response.status_code == 200
    [item] = response.json()["items"]
    assert set(item) == {
        "id", "chat_id", "start_date", "end_date", "days", "version", "status", "budget",
        "updated_at",
    }  # fmt: skip
    assert item["id"] == ready["trip_id"] and item["chat_id"] == chat["id"]
    assert item["days"] == 3 and item["version"] == 1 and item["status"] == "active"
    assert item["start_date"] == day(10) and item["end_date"] == day(12)
    assert item["budget"] == {
        "status": "ok",
        "budget_kzt": 900000,
        "total_kzt": ready["budget"]["total_kzt"],
    }
    assert item["updated_at"].endswith("+05:00")
    paged = await chat_env.client.get(
        "/v1/trips", headers=headers, params={"before": "2000-01-01T00:00:00Z", "limit": 5}
    )
    assert paged.json() == {"items": []}


async def test_get_trip_returns_everything_the_full_map_needs(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn, must_haves=["Плов-центр"])
    first_place = (await fetch_one(conn, "SELECT place_id FROM trip_items WHERE ord = 1 LIMIT 1"))[
        "place_id"
    ]
    photo = await fetch_one(
        conn,
        "INSERT INTO place_photos (place_id, storage_key) VALUES (%s, 'first.jpg') RETURNING id",
        (first_place,),
    )
    response = await get(chat_env, headers, ready["trip_id"], "ru")
    assert response.status_code == 200, response.text
    trip = response.json()
    assert set(trip) == {
        "id", "chat_id", "version", "status", "start_date", "end_date", "budget_kzt",
        "total_cost_kzt", "budget_choice", "weather_checked_at", "created_at", "updated_at",
        "days", "budget", "warnings", "must_have_unmet", "events",
    }  # fmt: skip
    assert trip["id"] == ready["trip_id"] and trip["version"] == 1
    assert trip["total_cost_kzt"] == ready["budget"]["total_kzt"]
    assert [d["date"] for d in trip["days"]] == [day(10), day(11), day(12)]
    assert trip["warnings"] == ready["warnings"] and trip["must_have_unmet"] == []

    first = trip["days"][0]["items"][0]
    assert set(first) == {
        "id", "ord", "kind", "meal", "place", "starts_at", "ends_at", "visit_min", "must_have",
        "est_cost_kzt", "cost_assumed", "hours_assumed", "rain_exposed",
    }  # fmt: skip
    assert set(first["place"]) == {
        "id", "name", "name_lang", "category", "category_name", "lat", "lon", "photo",
    }  # fmt: skip
    assert first["starts_at"].endswith("+05:00")
    all_items = [i for d in trip["days"] for i in d["items"]]
    assert any(i["must_have"] and i["place"]["name"] == "Плов-центр" for i in all_items)
    assert all(i["place"]["name_lang"] == "ru" for i in all_items)
    with_photo = [i for i in all_items if i["place"]["id"] == str(first_place)]
    assert with_photo and all(
        i["place"]["photo"]
        == {"id": str(photo["id"]), "storage_key": "first.jpg", "url": None}  # no MEDIA_BASE_URL
        for i in with_photo
    )
    assert all(i["place"]["photo"] is None for i in all_items if i not in with_photo)
    for d in trip["days"]:
        items = d["items"]
        assert [i["ord"] for i in items] == list(range(1, len(items) + 1))
        assert [leg["to_item_id"] for leg in d["legs"]] == [i["id"] for i in items[1:]]
        for leg in d["legs"]:
            assert set(leg) == {
                "id", "from_item_id", "to_item_id", "depart_at", "travel_s", "estimated",
                "chosen_mode", "cost_kzt", "options",
            }  # fmt: skip
            assert leg["chosen_mode"] in {o["mode"] for o in leg["options"]}
            assert all("geometry" in o and "cost_kzt_max" in o for o in leg["options"])
    assert trip["budget"]["status"] == "ok" and trip["budget"]["variants"] is None
    assert trip["budget"]["lodging"]["options"] == []
    # English names when asked in English
    en = (await get(chat_env, headers, ready["trip_id"], "en")).json()
    assert {i["place"]["name_lang"] for d in en["days"] for i in d["items"]} <= {"ru", "en"}


async def test_get_trip_shows_only_the_plan_and_the_choice_via_the_budget(chat_env, conn):
    headers, chat, ready, total = await over_budget_trip(
        chat_env, conn, 9000, must_haves=["Музей Кастеева"]
    )
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    stored_variants = await fetch_all(
        conn, "SELECT DISTINCT variant FROM trip_items WHERE trip_id = %s", (ready["trip_id"],)
    )
    assert {r["variant"] for r in stored_variants} == {"main", "drop_places", "cheaper"}
    plan_ids = {i["id"] for d in trip["days"] for i in d["items"]}
    main_ids = {
        str(r["id"])
        for r in await fetch_all(
            conn,
            "SELECT id FROM trip_items WHERE trip_id = %s AND variant = 'main'",
            (ready["trip_id"],),
        )
    }
    assert plan_ids == main_ids  # variants never leak into the days
    leg_ids = {leg["id"] for d in trip["days"] for leg in d["legs"]}
    assert leg_ids == {
        str(r["id"])
        for r in await fetch_all(
            conn,
            "SELECT id FROM trip_legs WHERE trip_id = %s AND variant = 'main'",
            (ready["trip_id"],),
        )
    }
    budget = trip["budget"]
    assert budget["status"] == "over" and budget["shortfall_kzt"] == 9000
    drop, cheaper = budget["variants"]["drop_places"], budget["variants"]["cheaper"]
    # same names and numbers as the `route_ready` event had
    assert drop["removed"] and drop["removed_count"] == len(drop["removed"])
    assert {r["name"] for r in drop["removed"]} == {
        r["name"] for r in ready["budget"]["variants"]["drop_places"]["removed"]
    }
    assert all(set(r) == {"id", "name", "name_lang", "category", "lat", "lon"}
               for r in drop["removed"])  # fmt: skip
    assert cheaper["swaps"] and cheaper["swaps_count"] == len(cheaper["swaps"])
    assert {(s["from"]["name"], s["to"]["name"]) for s in cheaper["swaps"]} == {
        (s["from"]["name"], s["to"]["name"])
        for s in ready["budget"]["variants"]["cheaper"]["swaps"]
    }
    assert drop["total_kzt"] <= budget["budget_kzt"] and cheaper["feasible"]
    assert "Музей Кастеева" not in {r["name"] for r in drop["removed"]}
    assert not UUID_RE.search(json.dumps(trip["budget"]["variants"]["drop_places"]["breakdown"]))


async def test_lodging_options_come_with_the_budget_when_there_is_no_lodging(chat_env, conn):
    await seed_world(conn)
    from app.routing import FakeRouter
    from tests.test_chat import new_chat

    chat_env.app.state.routing_provider = FakeRouter()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    from tests.test_trips import brief_call

    events, _ = await build(
        chat_env,
        headers,
        chat["id"],
        [
            Step(tool_calls=[brief_call(has_accommodation=False)]),
            Step(tool_calls=[call("build_trip", {})]),
        ],
    )
    ready = event(events, "route_ready")
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    options = trip["budget"]["lodging"]["options"]
    assert [o["id"] for o in options] == [
        o["place_id"] for o in ready["budget"]["lodging"]["options"]
    ]
    assert sum(o["recommended"] for o in options) == 1
    for o in options:
        assert o["nights"] == 2 and o["total_kzt"] == 2 * o["price_per_night_kzt"]
        assert {"name", "category", "lat", "lon", "rank", "price_assumed"} <= set(o)


async def test_choose_a_transport_mode_for_a_leg(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    leg = next(leg for d in trip["days"] for leg in d["legs"] if len(leg["options"]) > 1)
    other = next(o for o in leg["options"] if o["mode"] != leg["chosen_mode"])
    before_total = trip["budget"]["total_kzt"]

    response = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], leg["id"]),
        headers=headers,
        json={"mode": other["mode"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "trip_id", "version", "leg", "arrives_at", "late_by_s", "changed_days", "budget",
    }  # fmt: skip
    assert body["version"] == 2 and body["changed_days"] == [leg_day(trip, leg["id"])]
    assert body["leg"]["chosen_mode"] == other["mode"]
    assert body["leg"]["cost_kzt"] == other["cost_kzt_max"]
    assert body["late_by_s"] >= 0 and body["arrives_at"].endswith("+05:00")
    delta = other["cost_kzt_max"] - leg["cost_kzt"]
    assert body["budget"]["total_kzt"] == before_total + delta
    assert body["budget"]["breakdown"]["transport_kzt"] == (
        trip["budget"]["breakdown"]["transport_kzt"] + delta
    )

    again = (await get(chat_env, headers, ready["trip_id"])).json()
    assert again["version"] == 2 and again["total_cost_kzt"] == before_total + delta
    stored = [x for d in again["days"] for x in d["legs"] if x["id"] == leg["id"]][0]
    assert stored["chosen_mode"] == other["mode"] and stored["travel_s"] == body["leg"]["travel_s"]
    row = await fetch_one(conn, "SELECT total_cost_kzt, budget FROM trips")
    assert row["total_cost_kzt"] == row["budget"]["total_kzt"] == before_total + delta


def leg_day(trip, leg_id):
    for d in trip["days"]:
        if any(leg["id"] == leg_id for leg in d["legs"]):
            return d["date"]


async def test_a_mode_the_leg_does_not_offer_or_an_unknown_leg_is_refused(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    leg = trip["days"][0]["legs"][0]
    missing = next(
        m for m in ("walk", "scooter", "bus", "metro", "taxi", "car")
        if m not in {o["mode"] for o in leg["options"]}
    )  # fmt: skip
    url = "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], leg["id"])
    bad = await chat_env.client.post(url, headers=headers, json={"mode": missing})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    junk = await chat_env.client.post(url, headers=headers, json={"mode": "rocket"})
    assert junk.status_code == 422
    unknown = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], ready["trip_id"]),
        headers=headers,
        json={"mode": "walk"},
    )
    assert unknown.status_code == 404
    assert (await get(chat_env, headers, ready["trip_id"])).json()["version"] == 1
