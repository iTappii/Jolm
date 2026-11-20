from pathlib import Path

import import_popular
import psycopg
import pytest
from import_popular import CsvError, import_csv, parse_rows
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "popular_small.csv"
SEED = ROOT / "data" / "seed" / "categories.sql"
REAL_CSV = ROOT / "data" / "seed" / "popular_places.csv"


@pytest.fixture
def sconn(test_db_url):
    """Sync connection (the importers are sync scripts); rolled back after the test."""
    with psycopg.connect(test_db_url) as c:
        c.execute(SEED.read_text(encoding="utf-8"))
        yield c
        c.rollback()


def q(conn, query):
    """Run a query on a plain (tuple-row) connection and return dict rows."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        return cur.fetchall()


def test_import_small_fixture(sconn):
    stats = import_csv(sconn, FIXTURE)
    assert stats == {"inserted": 3, "updated": 0}
    rows = q(
        sconn,
        "SELECT p.*, c.slug AS cat, ST_Y(p.geom::geometry) AS lat FROM places p "
        "JOIN place_categories c ON c.id = p.category_id ORDER BY p.name_en",
    )
    assert [r["name_en"] for r in rows] == ["Cafe", "Medeu", "Republic Square"]
    medeu = rows[1]
    assert (medeu["osm_type"], medeu["osm_id"]) == ("node", 900001)
    assert medeu["cat"] == "mountain" and medeu["kind"] == "nature"
    assert medeu["is_mountain"] and medeu["elevation_m"] == 1691 and medeu["is_public"]
    assert medeu["typical_visit_min"] == 120 and medeu["setting"] == "outdoor"
    assert medeu["entry_price_kzt"] is None  # unknown stays NULL, never invented
    assert "entry_price_kzt" not in medeu["manual_override"]
    assert {"name_ru", "geom", "setting", "typical_visit_min"} <= set(medeu["manual_override"])
    assert rows[2]["entry_price_kzt"] == 0 and rows[2]["osm_id"] is None


def test_import_is_idempotent(sconn):
    import_csv(sconn, FIXTURE)
    stats = import_csv(sconn, FIXTURE)
    assert stats == {"inserted": 0, "updated": 3}
    assert q(sconn, "SELECT count(*) AS n FROM places")[0]["n"] == 3


def test_osm_reimport_does_not_overwrite_curated(sconn):
    from upsert import UPSERT_PLACE

    import_csv(sconn, FIXTURE)
    osm_rec = {
        "osm_type": "node", "osm_id": 900001, "lon": 77.0, "lat": 43.0, "category": "hotel",
        "kind": "accommodation", "name_ru": "Медеу (OSM)", "name_en": "OSM name",
        "name_kk": "Медеу",
        "address_ru": None, "address_en": None, "website": None, "is_public": False,
        "is_mountain": False, "elevation_m": 5, "setting": "indoor",
    }  # fmt: skip
    sconn.execute(UPSERT_PLACE, osm_rec)
    row = q(
        sconn,
        "SELECT p.name_ru, p.name_en, p.name_kk, p.elevation_m, p.setting, c.slug, "
        "ST_Y(p.geom::geometry) AS lat FROM places p JOIN place_categories c ON c.id=p.category_id "
        "WHERE osm_id = 900001",
    )[0]
    # curated fields survive; fields the curator did not set (name_kk) come from OSM
    assert row["name_ru"] == "Медеу" and row["name_en"] == "Medeu"
    assert row["elevation_m"] == 1691 and row["setting"] == "outdoor"
    assert row["slug"] == "mountain" and abs(row["lat"] - 43.1578) < 1e-6
    assert row["name_kk"] == "Медеу"


def test_validation(tmp_path):
    bad = tmp_path / "bad.csv"
    header = (
        "osm_type,osm_id,name_ru,name_en,lat,lon,category,description_ru,description_en,"
        "typical_visit_min,entry_price_kzt,avg_check_kzt,setting,is_mountain,elevation_m,"
        "is_public,popularity\n"
    )
    bad.write_text(header + ",,A,A,43.2,76.9,park,,,,,,outdoor,0,,1,1\n", encoding="utf-8")
    with pytest.raises(CsvError, match="typical_visit_min"):
        parse_rows(bad)
    bad.write_text(header + ",,A,A,43.2,76.9,park,,,30,,,underwater,0,,1,1\n", encoding="utf-8")
    with pytest.raises(CsvError, match="setting"):
        parse_rows(bad)
    bad.write_text(header + ",,A,A,43.2,76.9,nope,,,30,,,outdoor,0,,1,1\n", encoding="utf-8")
    with pytest.raises(CsvError, match="category"):
        parse_rows(bad)


def test_real_csv_is_valid_and_complete(sconn):
    rows = parse_rows(REAL_CSV)
    assert len(rows) >= 100
    assert all(r["typical_visit_min"] > 0 and r["setting"] for r in rows)
    import_csv(sconn, REAL_CSV)
    n = q(
        sconn,
        "SELECT count(*) AS n FROM places "
        "WHERE typical_visit_min IS NOT NULL AND setting IS NOT NULL",
    )[0]["n"]
    assert n == len(rows)


def test_sql_uses_named_parameters_only():
    assert "%(name_ru)s" in import_popular.UPSERT_OSM
    assert "name_ru'" not in import_popular.INSERT_MANUAL


# --- linking manual rows to OSM objects ------------------------------------------------------

LINK_HEADER = (
    "osm_type,osm_id,name_ru,name_en,lat,lon,category,description_ru,description_en,"
    "typical_visit_min,entry_price_kzt,avg_check_kzt,setting,is_mountain,elevation_m,"
    "is_public,popularity\n"
)
MANUAL_ROW = (
    ",,Площадь Республики,Republic Square,43.2380,76.9456,landmark,,,30,0,,outdoor,0,,1,95\n"
)
LINKED_ROW = (
    "way,597984193,Площадь Республики,Republic Square,43.2386,76.9456,landmark,,,30,0,,"
    "outdoor,0,,1,95\n"
)


def _csv(tmp_path, name, row):
    path = tmp_path / name
    path.write_text(LINK_HEADER + row, encoding="utf-8")
    return path


def _places(conn):
    return q(conn, "SELECT id, osm_type, osm_id, name_ru FROM places ORDER BY name_ru")


def test_manual_row_gets_osm_id_attached(sconn, tmp_path):
    import_csv(sconn, _csv(tmp_path, "m.csv", MANUAL_ROW))
    before = _places(sconn)
    assert len(before) == 1 and before[0]["osm_id"] is None
    stats = import_csv(sconn, _csv(tmp_path, "l.csv", LINKED_ROW))
    after = _places(sconn)
    assert len(after) == 1  # no duplicate
    assert after[0]["id"] == before[0]["id"]  # the same row, now linked
    assert (after[0]["osm_type"], after[0]["osm_id"]) == ("way", 597984193)
    assert stats["attached"] == 1
    # idempotent afterwards
    stats = import_csv(sconn, _csv(tmp_path, "l.csv", LINKED_ROW))
    assert stats == {"inserted": 0, "updated": 1} and len(_places(sconn)) == 1


def test_manual_row_merged_into_existing_osm_row(sconn, tmp_path):
    import_csv(sconn, _csv(tmp_path, "m.csv", MANUAL_ROW))
    manual_id = _places(sconn)[0]["id"]
    sconn.execute(
        "INSERT INTO place_hours (place_id, weekday, opens, closes) "
        "VALUES (%s, 1, '09:00', '18:00')",
        (manual_id,),
    )
    # the OSM importer already created its own row for the same object
    sconn.execute(
        "INSERT INTO places (osm_type, osm_id, name_ru, geom) VALUES "
        "('way', 597984193, 'Республика алаңы', "
        "ST_SetSRID(ST_MakePoint(76.9455, 43.2385), 4326)::geography)"
    )
    stats = import_csv(sconn, _csv(tmp_path, "l.csv", LINKED_ROW))
    rows = _places(sconn)
    assert len(rows) == 1 and rows[0]["osm_id"] == 597984193
    assert rows[0]["name_ru"] == "Площадь Республики"  # curated name wins
    assert stats["merged"] == 1
    # dependent rows follow the surviving row
    hours = q(sconn, "SELECT place_id FROM place_hours")
    assert [h["place_id"] for h in hours] == [rows[0]["id"]]


def test_far_or_differently_named_manual_row_is_left_alone(sconn, tmp_path):
    far = MANUAL_ROW.replace("43.2380,76.9456", "43.3500,76.9456")
    import_csv(sconn, _csv(tmp_path, "m.csv", far))
    import_csv(sconn, _csv(tmp_path, "l.csv", LINKED_ROW))
    assert len(_places(sconn)) == 2


def test_real_csv_manual_rows_have_no_osm_twin():
    """Every curated place exists in OSM, so none of them stays a manual row."""
    manual = [r for r in parse_rows(REAL_CSV) if r["osm_type"] is None]
    assert manual == []
