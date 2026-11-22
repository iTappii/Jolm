"""Ш-57 (server): regions table and module, `GET /v1/regions`, no city constants in the code."""

import re
from pathlib import Path

import pytest

from app import regions
from app.regions.seed import ALMATY

APP = Path(__file__).resolve().parents[1] / "app"

# Files of `server/app` that may name the first region. Everything else must get the city, the
# time zone and the box from `app.regions`. Each entry says why it is allowed.
ALLOWED = {
    "regions/seed.py",  # the built-in copy of the first region (compared with the DB row below)
    "planner/outside.py",  # data: the oblast name "Almaty Region" in the list of known places
}
FORBIDDEN = re.compile(r"ALMATY_|Asia/Almaty|\bAlmaty\b")
SUFFIXES = {".py", ".html", ".sql", ".js", ".json"}
VERSIONED = re.compile(r"^(?P<name>.+)\.(?P<locale>[a-z]{2})\.v(?P<n>\d+)\.md$")


@pytest.fixture(autouse=True)
def fresh_cache():
    regions.reset_cache()
    yield
    regions.reset_cache()


def test_no_city_constants_in_server_code():
    bad = []
    for path in sorted(APP.rglob("*")):
        rel = path.relative_to(APP).as_posix()
        if path.suffix not in SUFFIXES or "__pycache__" in rel or rel in ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                bad.append(f"{rel}:{number}: {line.strip()[:80]}")
    assert not bad, "city constants outside the region module:\n" + "\n".join(bad)


def test_latest_prompt_versions_do_not_name_the_city():
    latest = {}
    for path in (APP / "chat" / "prompts").glob("*.md"):
        m = VERSIONED.match(path.name)
        key = (m["name"], m["locale"])
        if m and int(m["n"]) > latest.get(key, (0, None))[0]:
            latest[key] = (int(m["n"]), path)
    assert latest
    for _, path in latest.values():
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        assert "Almaty" not in text and "Алматы" not in text, path.name


def test_default_region_is_the_seed_until_loaded():
    region = regions.default_region()
    assert region is ALMATY and region.is_default
    assert region.tz.key == "Asia/Almaty" and region.currency == "KZT"
    assert regions.get_region("almaty") is ALMATY and regions.get_region("nope") is None


async def test_database_row_equals_the_seed(conn):
    loaded = await regions.load_regions(conn)
    assert loaded == [ALMATY]


async def test_refresh_fills_the_cache_and_keeps_the_seed_when_empty(conn):
    assert [r.id for r in await regions.refresh(conn)] == ["almaty"]
    assert regions.default_region() == ALMATY
    await conn.execute("DELETE FROM regions")
    assert await regions.refresh(conn) == []
    assert regions.default_region() is ALMATY  # a bare database still starts


async def test_region_for_point_inside_and_outside(conn):
    for lat, lon in ((43.2389, 76.9455), (43.05, 77.05), (42.95, 76.70)):  # centre, Medeu, a corner
        found = await regions.region_for_point(conn, lat, lon)
        assert found is not None and found.id == "almaty"
    for lat, lon in ((51.13, 71.43), (43.2389, 77.4), (42.9, 76.9)):  # Astana, east, south
        assert await regions.region_for_point(conn, lat, lon) is None
    assert ALMATY.contains(43.2389, 76.9455) and not ALMATY.contains(51.13, 71.43)


async def test_region_for_point_prefers_the_smaller_region(conn):
    await conn.execute(
        "INSERT INTO regions (id, name_ru, name_en, boundary, timezone, currency, languages,"
        " centre_lat, centre_lon, camera_zoom)"
        " VALUES ('old-town', 'Старый город', 'Old town',"
        " ST_MakeEnvelope(76.9, 43.2, 77.0, 43.3, 4326),"
        " 'Asia/Almaty', 'KZT', ARRAY['ru'], 43.25, 76.95, 14)"
    )
    found = await regions.region_for_point(conn, 43.25, 76.95)
    assert found is not None and found.id == "old-town"


async def test_only_one_default_region(conn):
    import psycopg

    with pytest.raises(psycopg.errors.UniqueViolation):
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO regions (id, name_ru, name_en, boundary, timezone, currency,"
                " languages, centre_lat, centre_lon, camera_zoom, is_default)"
                " VALUES ('two', 'Два', 'Two', ST_MakeEnvelope(0, 0, 1, 1, 4326), 'UTC', 'USD',"
                " ARRAY['en'], 0.5, 0.5, 8, true)"
            )


async def test_regions_endpoint_has_the_agreed_shape(client):
    response = await client.get("/v1/regions")  # public: no authorization header
    assert response.status_code == 200
    assert response.json() == {
        "regions": [
            {
                "id": "almaty",
                "name": {"ru": "Алматы", "en": "Almaty"},
                "timezone": "Asia/Almaty",
                "currency": "KZT",
                "languages": ["ru", "en"],
                "centre": {"lat": 43.2389, "lon": 76.9455},
                "camera": {"zoom": 11.0},
                "bbox": [76.7, 42.95, 77.3, 43.45],
                "is_default": True,
            }
        ]
    }
