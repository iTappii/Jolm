"""Ш-42 (server): GET /v1/trips/{id}/offline."""

from app.config import get_settings
from tests.test_chat import sign_in
from tests.test_trips_read import built, get


async def offline(env, headers, trip_id, lang=None, **extra):
    h = dict(headers, **extra, **({"Accept-Language": lang} if lang else {}))
    return await env.client.get("/v1/trips/%s/offline" % trip_id, headers=h)


async def test_offline_copy_has_times_places_and_leg_paths(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    full = (await get(chat_env, headers, ready["trip_id"], "en")).json()
    response = await offline(chat_env, headers, ready["trip_id"], "en")
    assert response.status_code == 200, response.text
    body = response.json()
    assert response.headers["etag"] == '"v1-en"'
    assert response.headers["cache-control"] == "private, no-cache"
    assert set(body) == {
        "trip_id", "version", "locale", "timezone", "geometry_encoding", "start_date",
        "end_date", "budget_kzt", "total_cost_kzt", "days", "places",
    }  # fmt: skip
    assert (
        body["version"] == 1 and body["locale"] == "en" and body["geometry_encoding"] == "polyline6"
    )
    assert [d["date"] for d in body["days"]] == [d["date"] for d in full["days"]]
    for day, ref in zip(body["days"], full["days"]):
        assert [i["id"] for i in day["items"]] == [i["id"] for i in ref["items"]]
        for item, ref_item in zip(day["items"], ref["items"]):
            assert item["starts_at"] == ref_item["starts_at"] and item["place_id"] in body["places"]
            assert (
                item["starts_at"].endswith("+05:00") and item["visit_min"] == ref_item["visit_min"]
            )
        assert len(day["legs"]) == len(ref["legs"])
        for leg, ref_leg in zip(day["legs"], ref["legs"]):
            assert leg["mode"] == ref_leg["chosen_mode"] and leg["travel_s"] == ref_leg["travel_s"]
            assert leg["geometry"] and leg["distance_m"] is not None
            chosen = next(o for o in ref_leg["options"] if o["mode"] == leg["mode"])
            assert leg["geometry"] == chosen["geometry"]
    place = next(iter(body["places"].values()))
    assert {"name", "names", "category", "category_name", "lat", "lon", "address", "hours",
            "photo_url"} <= set(place)  # fmt: skip
    assert place["photo_url"] is None and "id" not in place
    assert len(body["places"]) == len({i["place_id"] for d in body["days"] for i in d["items"]})


async def test_offline_names_hours_address_and_photo_url(chat_env, conn, monkeypatch):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    item = trip["days"][0]["items"][0]
    pid = item["place"]["id"]
    await conn.execute(
        "UPDATE places SET name_en = 'Kasteev Museum', address_ru = 'ул. Кабанбай батыра 1', "
        "address_en = 'Kabanbay batyr 1' WHERE id = %s",
        (pid,),
    )
    await conn.execute(
        "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES "
        "(%s, 0, '10:00', '18:00'), (%s, 1, '10:00', '13:00'), (%s, 1, '14:00', '18:00')",
        (pid, pid, pid),
    )
    await conn.execute(
        "INSERT INTO place_photos (place_id, storage_key, source, status) "
        "VALUES (%s, 'p/a.jpg', 'osm', 'approved')",
        (pid,),
    )
    ru = (await offline(chat_env, headers, ready["trip_id"], "ru")).json()["places"][pid]
    en = (await offline(chat_env, headers, ready["trip_id"], "en")).json()["places"][pid]
    assert ru["address"] == "ул. Кабанбай батыра 1" and en["address"] == "Kabanbay batyr 1"
    assert (
        ru["names"]["en"] == en["names"]["en"] == "Kasteev Museum"
        and en["name"] == "Kasteev Museum"
    )
    assert ru["names"]["ru"] and ru["name"] == ru["names"]["ru"]
    assert en["hours"] == [
        {"weekday": 0, "intervals": [{"opens": "10:00", "closes": "18:00"}]},
        {"weekday": 1, "intervals": [{"opens": "10:00", "closes": "13:00"},
                                     {"opens": "14:00", "closes": "18:00"}]},
    ]  # fmt: skip
    assert en["photo_url"] is None  # no MEDIA_BASE_URL yet
    monkeypatch.setattr(get_settings(), "media_base_url", "https://media.example/")
    again = (await offline(chat_env, headers, ready["trip_id"], "en")).json()["places"][pid]
    assert again["photo_url"] == "https://media.example/p/a.jpg"


async def test_etag_gives_304_until_the_version_changes(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    tid = ready["trip_id"]
    first = await offline(chat_env, headers, tid, "en")
    etag = first.headers["etag"]
    for value in (etag, "W/" + etag, '"x", ' + etag, "*"):
        again = await offline(chat_env, headers, tid, "en", **{"If-None-Match": value})
        assert again.status_code == 304 and again.content == b""
        assert again.headers["etag"] == etag
    stale = await offline(chat_env, headers, tid, "en", **{"If-None-Match": '"v0-en"'})
    assert stale.status_code == 200
    # another language is another representation
    ru = await offline(chat_env, headers, tid, "ru", **{"If-None-Match": etag})
    assert ru.status_code == 200 and ru.headers["etag"] == '"v1-ru"'
    # an edit bumps the version: the old tag no longer matches
    trip = (await get(chat_env, headers, tid)).json()
    leg = next(leg for d in trip["days"] for leg in d["legs"] if len(leg["options"]) > 1)
    other = next(o for o in leg["options"] if o["mode"] != leg["chosen_mode"])
    edit = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (tid, leg["id"]),
        headers=headers,
        json={"mode": other["mode"]},
    )
    assert edit.status_code == 200
    after = await offline(chat_env, headers, tid, "en", **{"If-None-Match": etag})
    assert after.status_code == 200 and after.headers["etag"] == '"v2-en"'
    assert after.json()["version"] == 2
    changed = next(
        item for d in after.json()["days"] for item in d["legs"] if item["id"] == leg["id"]
    )
    assert changed["mode"] == other["mode"]


async def test_offline_requires_auth_and_hides_foreign_and_unknown_trips(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    tid = ready["trip_id"]
    c = chat_env.client
    assert (await c.get("/v1/trips/%s/offline" % tid)).status_code == 401
    other = await sign_in(conn, "other@example.com")
    foreign = await offline(chat_env, other, tid, **{"If-None-Match": '"v1-en"'})
    assert foreign.status_code == 404  # never 304 for someone else's trip
    missing = await offline(chat_env, headers, "00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert (await offline(chat_env, headers, "not-a-uuid")).status_code == 422
