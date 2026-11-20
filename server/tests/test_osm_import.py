from datetime import time
from pathlib import Path

from hours import parse_opening_hours
from tag_mapping import category_slug, classify, parse_elevation, pick_names
from upsert import UPSERT_PLACE, upsert_place

from app.db import fetch_one

SEED = Path(__file__).resolve().parents[2] / "data" / "seed" / "categories.sql"


# ---- tag mapping -------------------------------------------------------------------------


def test_cuisine_to_category():
    assert category_slug({"amenity": "restaurant", "cuisine": "chinese"}) == "cafe_chinese"
    assert category_slug({"amenity": "restaurant", "cuisine": "pizza;italian"}) == "cafe_european"
    assert category_slug({"amenity": "restaurant", "cuisine": "uzbek"}) == "cafe_oriental"
    assert category_slug({"amenity": "restaurant", "cuisine": "kazakh"}) == "cafe_kazakh"
    assert category_slug({"amenity": "restaurant"}) == "restaurant"
    assert category_slug({"amenity": "cafe"}) == "coffee"
    assert category_slug({"amenity": "cafe", "cuisine": "korean"}) == "cafe_korean"
    assert category_slug({"amenity": "fast_food", "cuisine": "burger"}) == "cafe_fast_food"


def test_other_tags():
    assert category_slug({"tourism": "museum"}) == "museum"
    assert category_slug({"leisure": "park"}) == "park"
    assert category_slug({"natural": "peak"}) == "mountain"
    assert category_slug({"natural": "water", "water": "lake"}) == "lake"
    assert category_slug({"shop": "mall"}) == "mall"
    assert category_slug({"shop": "supermarket"}) is None
    # noisy objects need an encyclopedic link
    assert category_slug({"historic": "memorial"}) is None
    assert category_slug({"historic": "memorial", "wikidata": "Q1"}) == "monument"
    assert category_slug({"amenity": "place_of_worship"}) is None


def test_unnamed_or_irrelevant_skipped():
    assert classify({"amenity": "cafe"}) is None
    assert classify({"name": "X", "highway": "bus_stop"}) is None


def test_names_by_script():
    ru, en, kk = pick_names({"name": "Кок-Тобе", "name:en": "Kok Tobe"})
    assert (ru, en, kk) == ("Кок-Тобе", "Kok Tobe", None)
    assert pick_names({"name": "Starbucks"}) == (None, "Starbucks", None)
    assert pick_names({"name": "Қазақ театры", "name:kk": "Қазақ театры"}) == (
        None,
        None,
        "Қазақ театры",
    )
    assert pick_names({"name": "A", "name:ru": "Б", "name:en": "A"}) == ("Б", "A", None)


def test_mountain_flag_and_elevation():
    peak = classify({"natural": "peak", "name": "Пик", "ele": "3680"})
    assert peak.is_mountain and peak.elevation_m == 3680 and peak.setting == "outdoor"
    view = classify({"tourism": "viewpoint", "name": "Вид", "ele": "900"})
    assert not view.is_mountain
    view = classify({"tourism": "viewpoint", "name": "Вид", "ele": "1500"})
    assert view.is_mountain
    assert parse_elevation("1 500") is None
    assert parse_elevation("1530.4 m") == 1530


def test_public_and_setting_defaults():
    museum = classify({"tourism": "museum", "name": "Музей"})
    assert museum.is_public and museum.setting == "indoor" and museum.kind == "venue"
    cafe = classify({"amenity": "cafe", "name": "Cafe"})
    assert not cafe.is_public


# ---- opening hours -----------------------------------------------------------------------


def test_hours_simple():
    h = parse_opening_hours("Mo-Fr 09:00-18:00; Sa,Su 10:00-16:00")
    assert len(h) == 7
    assert (0, time(9), time(18)) in h and (6, time(10), time(16)) in h


def test_hours_variants():
    assert len(parse_opening_hours("24/7")) == 7
    assert parse_opening_hours("24/7")[0] == (0, time(0), time(23, 59))
    assert len(parse_opening_hours("10:00-22:00")) == 7
    h = parse_opening_hours("Mo-Su 10:00-22:00; Sa off")
    assert {d for d, _, _ in h} == {0, 1, 2, 3, 4, 6}
    two = parse_opening_hours("Mo-Fr 09:00-13:00,14:00-18:00")
    assert len(two) == 10
    night = parse_opening_hours("Fr-Sa 18:00-02:00")
    assert (4, time(18), time(2)) in night and (5, time(18), time(2)) in night
    wrap = parse_opening_hours("Fr-Mo 10:00-20:00")
    assert {d for d, _, _ in wrap} == {4, 5, 6, 0}
    assert parse_opening_hours("Mo-Su 00:00-24:00")[0] == (0, time(0), time(23, 59))


def test_hours_unparsed():
    for bad in (
        None,
        "",
        "Mo-Fr 09:00-18:00; PH off",
        "sunrise-sunset",
        "Mar-Oct 09:00-18:00",
        "Mo-Fr 09:00+",
        "by appointment",
        "off",
        "Mo-Fr 9-18",
    ):
        assert parse_opening_hours(bad) is None, bad


# ---- upsert ------------------------------------------------------------------------------


def test_upsert_sql_is_static_and_parameterized():
    assert "%(name_ru)s" in UPSERT_PLACE and "ON CONFLICT (osm_type, osm_id)" in UPSERT_PLACE
    assert "manual_override @>" in UPSERT_PLACE


def record(**over):
    base = {
        "osm_type": "node", "osm_id": 42, "lon": 76.95, "lat": 43.25, "category": "park",
        "kind": "nature", "name_ru": "Парк", "name_en": "Park", "name_kk": None,
        "address_ru": None, "address_en": None, "website": None, "is_public": True,
        "is_mountain": False, "elevation_m": None, "setting": "outdoor",
    }  # fmt: skip
    base.update(over)
    return base


async def test_upsert_idempotent_and_respects_manual_override(conn):
    await conn.execute(SEED.read_text(encoding="utf-8"))
    # psycopg async conn: reuse the sync-style helper through run_sync-free path below
    pid, inserted = await _upsert(conn, record(), [(0, time(9), time(18))])
    assert inserted
    pid2, inserted2 = await _upsert(conn, record(name_en="Park 2"), [(1, time(8), time(9))])
    assert pid2 == pid and not inserted2
    row = await fetch_one(conn, "SELECT name_en FROM places WHERE id = %s", (pid,))
    assert row["name_en"] == "Park 2"
    hours = await (
        await conn.execute("SELECT weekday FROM place_hours WHERE place_id=%s", (pid,))
    ).fetchall()
    assert [h["weekday"] for h in hours] == [1]  # replaced, not appended

    # hand-edit: protect name_en and hours
    await conn.execute(
        "UPDATE places SET name_en = 'Hand', "
        'manual_override = \'["name_en", "hours"]\' WHERE id = %s',
        (pid,),
    )
    await _upsert(conn, record(name_en="OSM again", name_ru="Парк 3"), [(3, time(1), time(2))])
    row = await fetch_one(conn, "SELECT name_en, name_ru FROM places WHERE id = %s", (pid,))
    assert row == {"name_en": "Hand", "name_ru": "Парк 3"}
    hours = await (
        await conn.execute("SELECT weekday FROM place_hours WHERE place_id=%s", (pid,))
    ).fetchall()
    assert [h["weekday"] for h in hours] == [1]


async def _upsert(conn, rec, hours):
    """upsert_place is written for sync psycopg connections; run the same SQL on the async one."""
    from upsert import DELETE_HOURS, HOURS_FIELD, INSERT_HOURS

    cur = await conn.execute(UPSERT_PLACE, rec)
    row = await cur.fetchone()
    if hours and HOURS_FIELD not in (row["manual_override"] or []):
        await conn.execute(DELETE_HOURS, (row["id"],))
        for wd, o, c in hours:
            await conn.execute(INSERT_HOURS, (row["id"], wd, o, c))
    return row["id"], row["inserted"]


def test_upsert_place_is_exported():
    assert callable(upsert_place)
