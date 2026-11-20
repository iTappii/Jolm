from pathlib import Path

import psycopg
import pytest

from app.db import fetch_all, fetch_one
from app.places import sql

SEED = Path(__file__).resolve().parents[2] / "data" / "seed" / "categories.sql"


async def load_categories(conn):
    await conn.execute(SEED.read_text(encoding="utf-8"))


async def add_place(conn, name, lon, lat, category=None, status="active", popularity=0):
    row = await fetch_one(
        conn,
        """
        INSERT INTO places (name_ru, geom, category_id, status, popularity)
        VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                (SELECT id FROM place_categories WHERE slug = %s), %s, %s)
        RETURNING id
        """,
        (name, lon, lat, category, status, popularity),
    )
    return row["id"]


async def test_categories_seed_is_idempotent(conn):
    await load_categories(conn)
    first = await fetch_one(conn, "SELECT count(*) AS n FROM place_categories")
    await load_categories(conn)
    second = await fetch_one(conn, "SELECT count(*) AS n FROM place_categories")
    assert first["n"] == second["n"] >= 30
    row = await fetch_one(
        conn,
        "SELECT c.outdoor, p.slug AS parent FROM place_categories c "
        "JOIN place_categories p ON p.id = c.parent_id WHERE c.slug = %s",
        ("cafe_chinese",),
    )
    assert row == {"outdoor": False, "parent": "food"}


async def test_bbox_search(conn):
    await load_categories(conn)
    await add_place(conn, "Медеу", 77.0587, 43.1573, "mountain", popularity=90)
    await add_place(conn, "Кок-Тобе", 76.9747, 43.2330, "viewpoint", popularity=80)
    await add_place(conn, "Астана", 71.4300, 51.1280, "landmark")  # far outside
    await add_place(conn, "Закрыто", 76.9500, 43.2400, "cafe_kazakh", status="closed")

    almaty = (76.7, 43.0, 77.2, 43.4)
    rows = await fetch_all(conn, sql.BBOX_SEARCH, (*almaty, None, None, 50))
    assert [r["name_ru"] for r in rows] == ["Медеу", "Кок-Тобе"]  # popularity order, no closed
    assert rows[0]["category"] == "mountain"
    assert abs(rows[0]["lat"] - 43.1573) < 1e-6

    only_views = await fetch_all(conn, sql.BBOX_SEARCH, (*almaty, "viewpoint", "viewpoint", 50))
    assert [r["name_ru"] for r in only_views] == ["Кок-Тобе"]

    limited = await fetch_all(conn, sql.BBOX_SEARCH, (*almaty, None, None, 1))
    assert len(limited) == 1


async def test_bbox_uses_gist_index(conn):
    row = await fetch_one(
        conn,
        "SELECT indexdef FROM pg_indexes "
        "WHERE tablename = 'places' AND indexname = 'places_geom_gix'",
    )
    assert "gist" in row["indexdef"].lower()


async def test_constraints(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        await conn.execute(
            "INSERT INTO places (geom) VALUES (ST_SetSRID(ST_MakePoint(1, 1), 4326)::geography)"
        )


async def test_osm_unique(conn):
    ins = (
        "INSERT INTO places (osm_type, osm_id, name_en, geom) "
        "VALUES ('node', 1, 'x', ST_SetSRID(ST_MakePoint(1, 1), 4326)::geography)"
    )
    await conn.execute(ins)
    with pytest.raises(psycopg.errors.UniqueViolation):
        async with conn.transaction():
            await conn.execute(ins)
