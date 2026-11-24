from datetime import datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.db import fetch_one
from app.places import service
from tests.test_places import add_place, load_categories

TZ = ZoneInfo("Asia/Almaty")


def at(year, month, day, hh, mm=0):
    return datetime(year, month, day, hh, mm, tzinfo=TZ)


# 2026-11-23 is a Monday
MON, TUE = (2026, 11, 23), (2026, 11, 24)


# ------------------------------------------------------------ pure logic


def test_open_now_no_hours_is_none():
    assert service.is_open_now([], at(*MON, 12)) is None


def test_open_now_simple_and_multiple_intervals():
    hours = [(0, time(9), time(13)), (0, time(14), time(18))]
    assert service.is_open_now(hours, at(*MON, 10)) is True
    assert service.is_open_now(hours, at(*MON, 13, 30)) is False  # lunch break
    assert service.is_open_now(hours, at(*MON, 13)) is False  # closes is exclusive
    assert service.is_open_now(hours, at(*MON, 17, 59)) is True
    assert service.is_open_now(hours, at(*TUE, 10)) is False  # no Tuesday hours


def test_open_now_across_midnight():
    hours = [(0, time(20), time(2))]  # Mon 20:00 -> Tue 02:00
    assert service.is_open_now(hours, at(*MON, 23, 30)) is True
    assert service.is_open_now(hours, at(*TUE, 1, 30)) is True  # spill into Tuesday
    assert service.is_open_now(hours, at(*TUE, 2)) is False
    assert service.is_open_now(hours, at(*MON, 19, 59)) is False
    assert service.is_open_now(hours, at(*MON, 1)) is False  # Monday early: not Sunday's


def test_open_now_sunday_spills_into_monday():
    hours = [(6, time(22), time(3))]
    assert service.is_open_now(hours, at(2026, 11, 23, 2)) is True


def test_open_now_round_the_clock():
    hours = [(0, time(0), time(23, 59))]
    assert service.is_open_now(hours, at(*MON, 0)) is True
    assert service.is_open_now(hours, at(*MON, 23, 59)) is True
    assert service.is_open_now(hours, at(*TUE, 12)) is False  # only Monday listed


def test_open_now_converts_timezone():
    from datetime import timezone

    hours = [(0, time(9), time(18))]
    utc = datetime(2026, 11, 23, 5, 0, tzinfo=timezone.utc)  # 10:00 Almaty (UTC+5)
    assert service.is_open_now(hours, utc) is True


def test_pick_text_fallback_chain():
    row = {"name_ru": None, "name_en": "Park", "name_kk": "Саябақ"}
    assert service.pick_text(row, "name", "ru") == ("Park", "en")
    assert service.pick_text(
        {"name_ru": "Парк", "name_en": None, "name_kk": "K"}, "name", "en"
    ) == ("Парк", "ru")
    assert service.pick_text({"name_ru": " ", "name_en": "", "name_kk": "K"}, "name", "en") == (
        "K",
        "kk",
    )
    assert service.pick_text(
        {"description_ru": None, "description_en": None}, "description", "ru"
    ) == (None, None)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "1,2,3",
        "a,b,c,d",
        "76,43,75,44",
        "76,44,77,43",
        "-181,0,0,1",
        "0,-91,1,0",
        "0,0,50,1",
        "nan,0,1,1",
        "0,0,1,inf",
    ],
)
def test_parse_bbox_rejects(raw):
    with pytest.raises(ValueError):
        service.parse_bbox(raw)


def test_parse_bbox_ok():
    assert service.parse_bbox("76.85,43.2,77.0,43.3") == (76.85, 43.2, 77.0, 43.3)


def test_like_pattern_escapes():
    assert service.like_pattern("50%_a\\") == "%50\\%\\_a\\\\%"


# ------------------------------------------------------------ API

BBOX = "76.8,43.1,77.1,43.4"


async def set_names(conn, pid, **cols):
    for k, v in cols.items():
        assert k in ("name_ru", "name_en", "name_kk", "description_ru", "description_en")
        await conn.execute("UPDATE places SET %s = %%s WHERE id = %%s" % k, (v, pid))


async def test_places_bbox_category_limit_and_status(client, conn):
    await load_categories(conn)
    a = await add_place(conn, "Медеу", 77.0587, 43.1573, "mountain", popularity=90)
    await add_place(conn, "Кок-Тобе", 76.9747, 43.2330, "viewpoint", popularity=80)
    await add_place(conn, "Астана", 71.43, 51.128, "landmark")
    await add_place(conn, "Скрыто", 76.95, 43.24, "viewpoint", status="hidden")
    r = await client.get("/v1/places", params={"bbox": BBOX})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["name"] for i in items] == ["Медеу", "Кок-Тобе"]  # by popularity, active only
    assert items[0]["id"] == str(a)
    assert set(items[0]) == {
        "id",
        "name",
        "name_lang",
        "category",
        "kind",
        "lat",
        "lon",
        "is_public",
        "is_partner",
        "popularity",
        "rating",
        "today",
        "address",
        "logo_url",
    }
    r = await client.get("/v1/places", params={"bbox": BBOX, "category": "viewpoint"})
    assert [i["name"] for i in r.json()["items"]] == ["Кок-Тобе"]
    r = await client.get("/v1/places", params={"bbox": BBOX, "limit": 1})
    assert len(r.json()["items"]) == 1


async def test_places_category_parent_matches_children(client, conn):
    await load_categories(conn)
    await add_place(conn, "Китайка", 76.9, 43.2, "cafe_chinese")
    r = await client.get("/v1/places", params={"bbox": BBOX, "category": "food"})
    assert [i["name"] for i in r.json()["items"]] == ["Китайка"]


async def test_places_geojson(client, conn):
    await load_categories(conn)
    await add_place(conn, "Медеу", 77.0587, 43.1573, "mountain")
    r = await client.get("/v1/places", params={"bbox": BBOX, "format": "geojson"})
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["geometry"] == {"type": "Point", "coordinates": [77.0587, 43.1573]}
    assert body["features"][0]["properties"]["name"] == "Медеу"


async def test_places_localized_name_fallback(client, conn):
    only_en = await add_place(conn, "x", 76.9, 43.2)
    await set_names(conn, only_en, name_en="Green Park")
    await set_names(conn, only_en, name_ru=None)
    only_ru = await add_place(conn, "Зелёный рынок", 76.91, 43.21)
    only_kk = await add_place(conn, "x", 76.92, 43.22)
    await set_names(conn, only_kk, name_kk="Көктөбе")
    await set_names(conn, only_kk, name_ru=None)
    ru = {
        i["id"]: i
        for i in (
            await client.get("/v1/places", params={"bbox": BBOX}, headers={"Accept-Language": "ru"})
        ).json()["items"]
    }
    en = {
        i["id"]: i
        for i in (
            await client.get("/v1/places", params={"bbox": BBOX}, headers={"Accept-Language": "en"})
        ).json()["items"]
    }
    assert ru[str(only_en)]["name"] == "Green Park" and ru[str(only_en)]["name_lang"] == "en"
    assert en[str(only_ru)]["name"] == "Зелёный рынок" and en[str(only_ru)]["name_lang"] == "ru"
    assert ru[str(only_kk)]["name"] == "Көктөбе" and en[str(only_kk)]["name_lang"] == "kk"


async def test_places_search_ru_en_kk_with_and_without_bbox(client, conn):
    await load_categories(conn)
    cafe = await add_place(conn, "Кафе Достык", 76.95, 43.25, "cafe_kazakh", popularity=5)
    await set_names(conn, cafe, name_en="Dostyk Cafe", name_kk="Достық кафесі")
    other = await add_place(conn, "Парк Горького", 76.96, 43.26, "park")
    far = await add_place(conn, "Достык Астана", 71.4, 51.1)
    r = await client.get("/v1/places", params={"q": "достык"})
    ids = [i["id"] for i in r.json()["items"]]
    assert str(cafe) in ids and str(far) in ids and str(other) not in ids
    r = await client.get("/v1/places", params={"q": "Dostyk", "bbox": BBOX})
    assert [i["id"] for i in r.json()["items"]] == [str(cafe)]
    r = await client.get("/v1/places", params={"q": "Достық"})
    assert r.json()["items"][0]["id"] == str(cafe)  # exact KK match ranks first, fuzzy ones follow
    # typo still found through trigram similarity
    r = await client.get("/v1/places", params={"q": "Dostik Cafe", "bbox": BBOX})
    assert str(cafe) in [i["id"] for i in r.json()["items"]]
    # LIKE wildcards are plain characters
    r = await client.get("/v1/places", params={"q": "%%", "bbox": BBOX})
    assert r.json()["items"] == []


async def test_places_validation_errors(client):
    for params in (
        {"bbox": "1,2,3"},
        {"bbox": "77,43,76,44"},
        {"bbox": "0,0,50,50"},
        {"bbox": BBOX, "limit": 0},
        {"bbox": BBOX, "limit": 100000},
        {"bbox": BBOX, "format": "xml"},
        {"q": "a"},
        {},
    ):
        r = await client.get("/v1/places", params=params)
        assert r.status_code == 422, params
        assert r.json()["error"]["code"] == "validation_error"


async def test_place_detail_full(client, conn):
    await load_categories(conn)
    pid = await add_place(conn, "Медеу", 77.0587, 43.1573, "mountain")
    await conn.execute(
        "UPDATE places SET name_en='Medeu', description_ru='Каток', address_ru='ул. Горная',"
        " entry_price_kzt=1000, typical_visit_min=120, is_mountain=true, elevation_m=1691,"
        " setting='outdoor', website='https://example.org' WHERE id=%s",
        (pid,),
    )
    await conn.execute(
        "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES"
        " (%s,0,'09:00','13:00'),(%s,0,'14:00','18:00'),(%s,1,'00:00','23:59')",
        (pid, pid, pid),
    )
    await conn.execute(
        "INSERT INTO place_photos (place_id, storage_key, status) VALUES"
        " (%s,'a.jpg','approved'),(%s,'b.jpg','pending'),(%s,'c.jpg','rejected')",
        (pid, pid, pid),
    )
    await conn.execute(
        "INSERT INTO place_menu (place_id, payload) VALUES (%s, '{\"items\": []}')", (pid,)
    )
    r = await client.get("/v1/places/%s" % pid, headers={"Accept-Language": "ru"})
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Медеу" and d["names"] == {"ru": "Медеу", "en": "Medeu", "kk": None}
    assert d["description"] == "Каток" and d["address"] == "ул. Горная"
    assert d["category"]["slug"] == "mountain" and d["category"]["name"]
    assert d["prices"] == {
        "entry_price_kzt": 1000,
        "avg_check_kzt": None,
        "price_per_night_kzt": None,
    }
    assert d["is_mountain"] and d["elevation_m"] == 1691 and d["setting"] == "outdoor"
    assert [p["storage_key"] for p in d["photos"]] == ["a.jpg"]
    assert d["hours"] == [
        {
            "weekday": 0,
            "intervals": [
                {"opens": "09:00", "closes": "13:00"},
                {"opens": "14:00", "closes": "18:00"},
            ],
        },
        {"weekday": 1, "intervals": [{"opens": "00:00", "closes": "23:59"}]},
    ]
    assert isinstance(d["open_now"], bool)
    assert d["menu"]["payload"] == {"items": []}
    assert d["crowd"] is None and d["data_updated_at"]
    en = (await client.get("/v1/places/%s" % pid, headers={"Accept-Language": "en"})).json()
    assert en["name"] == "Medeu"
    assert en["description"] == "Каток"  # no EN description: falls back to RU


async def test_place_detail_minimal_has_null_open_now(client, conn):
    pid = await add_place(conn, "Без часов", 76.9, 43.2)
    d = (await client.get("/v1/places/%s" % pid)).json()
    assert d["open_now"] is None and d["hours"] == [] and d["photos"] == []
    assert d["menu"] is None and d["category"] is None


async def test_place_detail_404_and_422(client, conn):
    hidden = await add_place(conn, "Скрыто", 76.9, 43.2, status="hidden")
    closed = await add_place(conn, "Закрыто", 76.9, 43.2, status="closed")
    for pid in (hidden, closed, uuid4()):
        r = await client.get("/v1/places/%s" % pid)
        assert r.status_code == 404
        assert r.json() == {"error": {"code": "not_found", "message": "Not found"}}
    r = await client.get("/v1/places/not-a-uuid")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


async def test_categories(client, conn):
    await load_categories(conn)
    r = await client.get("/v1/categories", headers={"Accept-Language": "ru"})
    items = r.json()["items"]
    by = {c["slug"]: c for c in items}
    assert len(items) >= 30
    assert by["cafe_chinese"]["parent"] == "food" and by["food"]["parent"] is None
    assert set(by["food"]) == {"slug", "parent", "name", "outdoor", "sort_order"}
    en = (await client.get("/v1/categories", headers={"Accept-Language": "en"})).json()["items"]
    assert {c["slug"]: c["name"] for c in en} != {c["slug"]: c["name"] for c in items}


async def make_route(conn, status, places):
    row = await fetch_one(
        conn,
        "INSERT INTO curated_routes (title_ru, title_en, status)"
        " VALUES ('Маршрут','Route',%s) RETURNING id",
        (status,),
    )
    for n, pid in enumerate(places):
        await conn.execute(
            "INSERT INTO curated_route_items (route_id, place_id, ord) VALUES (%s,%s,%s)",
            (row["id"], pid, n),
        )
    return row["id"]


async def test_curated_routes_published_only(client, conn):
    a = await add_place(conn, "Первое", 76.9, 43.2)
    b = await add_place(conn, "Второе", 76.91, 43.21)
    gone = await add_place(conn, "Скрытое", 76.92, 43.22, status="hidden")
    pub = await make_route(conn, "published", [b, gone, a])
    draft = await make_route(conn, "draft", [a])
    r = await client.get("/v1/curated-routes", headers={"Accept-Language": "en"})
    items = r.json()["items"]
    assert [i["id"] for i in items] == [str(pub)]
    assert items[0]["title"] == "Route" and items[0]["places_count"] == 2
    d = (await client.get("/v1/curated-routes/%s" % pub)).json()
    assert [(i["ord"], i["name"]) for i in d["items"]] == [(0, "Второе"), (2, "Первое")]
    assert {"lat", "lon", "category", "is_partner"} <= set(d["items"][0])
    r = await client.get("/v1/curated-routes/%s" % draft)
    assert r.status_code == 404
    assert (await client.get("/v1/curated-routes/%s" % uuid4())).status_code == 404
    assert (await client.get("/v1/curated-routes/zzz")).status_code == 422
