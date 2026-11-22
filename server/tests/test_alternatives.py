"""Ш-55: GET /v1/trips/{id}/items/{item_id}/alternatives."""

from app.routing.fake import haversine_m
from tests.test_chat import sign_in
from tests.test_places import add_place
from tests.test_trip_edits import all_items, post
from tests.test_trips_read import built, get


def url(trip_id, item_id):
    return "/v1/trips/%s/items/%s/alternatives" % (trip_id, item_id)


async def fetch(env, headers, trip_id, item_id, lang=None):
    h = dict(headers, **({"Accept-Language": lang} if lang else {}))
    return await env.client.get(url(trip_id, item_id), headers=h)


async def test_alternatives_are_similar_nearby_and_not_in_the_trip(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    tid = ready["trip_id"]
    trip = (await get(chat_env, headers, tid)).json()
    items = all_items(trip)
    in_trip = {i["place"]["id"] for i in items}
    shown = 0
    for item in items:
        response = await fetch(chat_env, headers, tid, item["id"], "en")
        assert response.status_code == 200, response.text
        found = response.json()["items"]
        assert len(found) <= 5
        assert not ({f["id"] for f in found} & in_trip)  # never one already in the trip
        assert all(f["category"] == item["place"]["category"] for f in found)
        here = (item["place"]["lat"], item["place"]["lon"])
        for f in found:
            assert set(f) == {
                "id", "name", "category", "lat", "lon", "price_kzt", "distance_m",
            }  # fmt: skip
            assert isinstance(f["distance_m"], int)
            assert abs(f["distance_m"] - haversine_m(here, (f["lat"], f["lon"]))) < 2
            assert f["price_kzt"] is None or isinstance(f["price_kzt"], int)
        shown += bool(found)
    assert shown  # the seeded world has several places per category


async def test_alternative_can_replace_and_prices_follow_place_kind(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    tid = ready["trip_id"]
    items = all_items((await get(chat_env, headers, tid)).json())
    meal = next(i for i in items if i["kind"] == "meal" and not i["must_have"])
    for n in range(7):  # more unused places of the same category, 7 > the limit of 5
        pid = await add_place(
            conn, "Доп кафе %d" % n, 76.94 + n / 1000, 43.24, meal["place"]["category"], "active", 1
        )
        await conn.execute("UPDATE places SET avg_check_kzt = %s WHERE id = %s", (2000 + n, pid))
    found = (await fetch(chat_env, headers, tid, meal["id"])).json()["items"]
    assert len(found) == 5 and all(f["price_kzt"] for f in found)  # cafes: the average check
    assert all(f["name"].startswith("Доп кафе") for f in found)
    done = await post(chat_env, headers, tid, meal["id"], "replace", {"place_id": found[0]["id"]})
    assert done.status_code in (200, 409), done.text  # may not fit the day, never a 5xx


async def test_alternatives_errors(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    tid = ready["trip_id"]
    item = all_items((await get(chat_env, headers, tid)).json())[0]["id"]
    c = chat_env.client
    assert (await c.get(url(tid, item))).status_code == 401
    other = await sign_in(conn, "b@example.com")
    assert (await fetch(chat_env, other, tid, item)).status_code == 404  # foreign trip
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await fetch(chat_env, headers, tid, unknown)).status_code == 404
    assert (await fetch(chat_env, headers, unknown, item)).status_code == 404
