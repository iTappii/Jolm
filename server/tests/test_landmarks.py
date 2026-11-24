"""Ш-69: GET /v1/landmarks and the landmarks seed."""

import re
from pathlib import Path

from app.db import execute, fetch_all, fetch_one
from tests.test_places import add_place, load_categories

SEED = Path(__file__).resolve().parents[2] / "data" / "seed" / "landmarks.sql"

ICONS = {
    "mosque", "cathedral", "tv_tower", "skating_rink", "ski_cable_car", "bazaar", "park", "museum",
    "monument", "mausoleum", "canyon", "mountain_lake", "ferris_wheel", "theatre", "stadium",
    "square",
}  # fmt: skip

ALMATY = (76.9455, 43.2389)
TURKESTAN = (68.27, 43.30)


async def mark(conn, place_id, rank, min_zoom):
    await execute(
        conn,
        "INSERT INTO landmarks (place_id, rank, min_zoom, icon, source, as_of) "
        "VALUES (%s, %s, %s, 'park', 'test', DATE '2026-11-24')",
        (place_id, rank, min_zoom),
    )


async def set_names(conn, place_id, name_ru, name_en):
    await execute(
        conn, "UPDATE places SET name_ru = %s, name_en = %s WHERE id = %s",
        (name_ru, name_en, place_id),
    )  # fmt: skip


async def test_shape_order_and_localization(client, conn):
    await load_categories(conn)
    a2 = await add_place(conn, "Б", *ALMATY, category="park")
    a1 = await add_place(conn, "А", 77.06, 43.16, category="mountain")
    t1 = await add_place(conn, "Т", *TURKESTAN, category="historic")
    await set_names(conn, a1, "Медеу", "Medeu")
    await mark(conn, a2, 2, 13.0)
    await mark(conn, a1, 1, 12.0)
    await mark(conn, t1, 1, 11.5)

    r = await client.get("/v1/landmarks", headers={"Accept-Language": "en"})
    assert r.status_code == 200
    items = r.json()["landmarks"]
    assert [(i["region"], i["rank"]) for i in items] == [
        ("almaty", 1), ("almaty", 2), ("kazakhstan", 1)
    ]  # fmt: skip
    first = items[0]
    assert set(first) == {
        "id",
        "name",
        "category",
        "lat",
        "lon",
        "min_zoom",
        "rank",
        "icon",
        "region",
    }
    assert first["id"] == str(a1)
    assert first["name"] == "Medeu"
    assert first["category"] == "mountain"
    assert first["min_zoom"] == 12.0
    assert first["icon"] == "park"
    assert abs(first["lat"] - 43.16) < 1e-6 and abs(first["lon"] - 77.06) < 1e-6
    assert items[1]["name"] == "Б"  # no English name: falls back to Russian

    ru = (await client.get("/v1/landmarks", headers={"Accept-Language": "ru"})).json()
    assert ru["landmarks"][0]["name"] == "Медеу"

    card = await client.get("/v1/places/%s" % first["id"])  # id works with the place card
    assert card.status_code == 200


async def test_inactive_place_is_hidden(client, conn):
    await load_categories(conn)
    pid = await add_place(conn, "Закрыто", *ALMATY, category="park", status="hidden")
    await mark(conn, pid, 1, 12.0)
    assert (await client.get("/v1/landmarks")).json() == {"landmarks": []}


async def test_cache_headers_and_etag(client, conn):
    await load_categories(conn)
    await mark(conn, await add_place(conn, "А", *ALMATY, category="park"), 1, 12.0)
    r = await client.get("/v1/landmarks")
    assert r.headers["cache-control"] == "public, max-age=3600"
    etag = r.headers["etag"]
    again = await client.get("/v1/landmarks", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag
    other = await client.get("/v1/landmarks", headers={"If-None-Match": '"stale"'})
    assert other.status_code == 200


async def test_seed_skips_missing_places_and_is_idempotent(conn):
    await load_categories(conn)
    # empty database: every row is skipped with a warning, nothing fails
    await conn.execute(SEED.read_text(encoding="utf-8"))
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM landmarks"))["n"] == 0

    await execute(
        conn,
        "INSERT INTO places (osm_type, osm_id, name_ru, geom) VALUES "
        "('node', 4665038995, 'Медеу', "
        "ST_SetSRID(ST_MakePoint(77.0596, 43.1578), 4326)::geography)",
    )
    await execute(
        conn,
        "INSERT INTO places (name_ru, geom) VALUES "
        "('Кольсайские озёра', ST_SetSRID(ST_MakePoint(78.33, 42.99), 4326)::geography)",
    )
    for _ in range(2):  # twice: idempotent
        await conn.execute(SEED.read_text(encoding="utf-8"))
        rows = await fetch_all(
            conn, "SELECT p.name_ru, l.rank, l.min_zoom, l.source FROM landmarks l "
            "JOIN places p ON p.id = l.place_id ORDER BY l.rank",
        )  # fmt: skip
        assert [(r["name_ru"], r["rank"], r["min_zoom"]) for r in rows] == [
            ("Медеу", 1, 12.0), ("Кольсайские озёра", 3, 11.5)
        ]  # fmt: skip
        assert {r["source"] for r in rows} == {"jol_seed"}


def test_seed_zoom_and_icon_rules():
    """No label before zoom 11.5 (Almaty overview ~11 shows none); every icon is a known key."""
    text = SEED.read_text(encoding="utf-8")
    rows = re.findall(r"(\d+\.\d+)(?:::real)?, '([a-z_]+)'\)", text)
    assert len(rows) == 12
    assert min(float(z) for z, _ in rows) >= 11.5
    assert {i for _, i in rows} <= ICONS
