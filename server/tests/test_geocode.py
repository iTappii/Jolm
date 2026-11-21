"""Ш-23c (server): OSM address import and reverse geocoding from our own data."""

from pathlib import Path

import import_addresses
import psycopg
import pytest

from app.db import execute, fetch_all, fetch_one
from tests.test_places import add_place

FIXTURE = Path(__file__).parent / "fixtures" / "osm" / "addresses.osm"
URL = "/v1/geocode/reverse"


# --- import -----------------------------------------------------------------------------------


def test_build_record_keeps_numbers_and_named_buildings_only():
    keep = import_addresses.build_record
    assert keep("node", 1, 76.9, 43.2, {"building": "yes"}) is None
    assert keep("way", 1, 76.9, 43.2, {"building": "yes"}) is None
    # a name alone is enough only for a building way, not for a node
    assert keep("node", 1, 76.9, 43.2, {"name": "Кафе"}) is None
    named = keep("way", 7, 76.9, 43.2, {"building": "retail", "name": "ТРЦ", "name:en": "Mall"})
    assert named[4] is None and named[8:11] == ("ТРЦ", "Mall", None) and named[11] == "retail"
    numbered = keep(
        "node", 8, 76.9, 43.2, {"addr:housenumber": " 12 ", "addr:street": "Төле би көшесі"}
    )
    assert numbered[4] == "12" and numbered[5:8] == (None, None, "Төле би көшесі")


def test_extract_fixture():
    rows = {(r[0], r[1]): r for r in import_addresses.extract(FIXTURE)}
    assert set(rows) == {("node", 1), ("way", 100), ("way", 101)}  # no bare building, no Astana
    assert rows[("node", 1)][5] == "проспект Абая"
    assert rows[("way", 100)][3] == pytest.approx(43.2601)  # centroid of the way's nodes
    assert rows[("way", 101)][5:8] == (None, "Tole Bi street", "Төле би көшесі")


@pytest.fixture
def sconn(test_db_url):
    with psycopg.connect(test_db_url) as c:
        yield c
        c.rollback()


def test_import_is_idempotent_and_removes_vanished_rows(sconn):
    records = list(import_addresses.extract(FIXTURE))
    first = import_addresses.load(sconn, iter(records))
    second = import_addresses.load(sconn, iter(records))
    assert first["upserted"] == 3
    assert second["upserted"] == 0 and second["deleted"] == 0  # nothing changed, nothing touched
    assert sconn.execute("SELECT count(*) FROM osm_addresses").fetchone()[0] == 3
    stats = import_addresses.load(sconn, iter(records[:1]))
    assert stats["deleted"] == 2
    assert sconn.execute("SELECT count(*) FROM osm_addresses").fetchone()[0] == 1


# --- API --------------------------------------------------------------------------------------


async def load_fixture(conn):
    for r in import_addresses.extract(FIXTURE):
        await execute(
            conn,
            "INSERT INTO osm_addresses (osm_type, osm_id, geom, housenumber, street_ru, street_en,"
            " street_kk, name_ru, name_en, name_kk, building)"
            " VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,"
            " %s, %s, %s, %s, %s, %s, %s, %s)",
            (r[0], r[1], r[2], r[3], *r[4:]),
        )


async def test_place_wins_inside_radius(client, conn):
    await load_fixture(conn)
    near = await add_place(conn, "Кафе", 76.9500, 43.2500)
    await add_place(conn, "Дальнее", 76.9510, 43.2500)  # ~80 m away
    hidden = await add_place(conn, "Скрытое", 76.95001, 43.25001, status="hidden")
    response = await client.get(URL, params={"lat": 43.25002, "lon": 76.95002})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "place"
    assert body["place"]["id"] == str(near) and body["place"]["id"] != str(hidden)
    assert body["place"]["name"] == "Кафе"
    assert body["distance_m"] <= 3
    assert "max-age" in response.headers["Cache-Control"]


async def test_address_when_no_place_close(client, conn):
    await load_fixture(conn)
    await add_place(conn, "Дальнее", 76.9510, 43.2500)
    ru = (await client.get(URL, params={"lat": 43.25005, "lon": 76.9500})).json()
    assert ru["kind"] == "address" and ru["address"] == "проспект Абая 10"
    assert ru["name"] is None and abs(ru["lat"] - 43.25) < 1e-6
    # locale fallback chain: en -> ru -> kk, with the explicit English street when present
    tap = {"lat": 43.2701, "lon": 76.9701}
    ru2 = (await client.get(URL, params=tap, headers={"Accept-Language": "ru"})).json()
    en = (await client.get(URL, params=tap, headers={"Accept-Language": "en"})).json()
    assert ru2["address"] == "Tole Bi street 5А"  # ru chain is ru, en, kk: the :en street wins
    assert en["address"] == "Tole Bi street 5А"
    mall = (
        await client.get(
            URL, params={"lat": 43.2601, "lon": 76.9601}, headers={"Accept-Language": "en"}
        )
    ).json()
    assert mall["kind"] == "address" and mall["name"] == "Test Mall" and mall["address"] is None


async def test_bare_point_and_validation(client, conn):
    await load_fixture(conn)
    far = await client.get(URL, params={"lat": 43.30, "lon": 77.10})
    assert far.json() == {"kind": "point", "lat": 43.30, "lon": 77.10}
    for params in [
        {"lat": 51.1, "lon": 71.4},  # Astana: outside Almaty
        {"lat": 91, "lon": 76.9},
        {"lat": 43.2},
        {"lat": "x", "lon": 76.9},
    ]:
        assert (await client.get(URL, params=params)).status_code == 422


async def test_rate_limit_carries_retry_after(client, conn):
    from app.geocode import api

    client._transport.app.state.geocode_limiter.limit = 2
    params = {"lat": 43.25, "lon": 76.95}
    assert (await client.get(URL, params=params)).status_code == 200
    assert (await client.get(URL, params=params)).status_code == 200
    third = await client.get(URL, params=params)
    assert third.status_code == 429 and int(third.headers["Retry-After"]) >= 1
    assert api.LIMIT_PER_MINUTE == 120


async def test_import_table_is_independent_of_places(conn):
    # no place_id column: TECH_PLAN rule 8 (merge_place) does not apply
    cols = await fetch_all(
        conn,
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'osm_addresses'",
    )
    assert "place_id" not in {c["column_name"] for c in cols}
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM places"))["n"] >= 0
