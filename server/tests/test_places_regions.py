"""Ш-58: places by region. Field sources and priority, merging OSM + Overture + Foursquare,
the region boundary filter, Parquet readers, the coverage report. No network: tiny fixtures."""

from pathlib import Path

import open_sources
import place_load as load
import place_match as match
import place_region as region_mod
import psycopg
import pytest
import region_coverage as coverage
from merge import merge_place
from psycopg.rows import dict_row
from upsert import upsert_place

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "seed" / "categories.sql"


@pytest.fixture
def sconn(test_db_url):
    with psycopg.connect(test_db_url) as c:
        c.execute(SEED.read_text(encoding="utf-8"))
        yield c
        c.rollback()


def q(conn, query, params=None):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def osm_record(osm_id, name_ru, lon=76.9, lat=43.2, **extra):
    rec = {
        "osm_type": "node", "osm_id": osm_id, "lon": lon, "lat": lat, "category": "coffee",
        "kind": "venue", "name_ru": name_ru, "name_en": None, "name_kk": None,
        "address_ru": None, "address_en": None, "website": None, "is_public": False,
        "is_mountain": False, "elevation_m": None, "setting": "indoor",
    }  # fmt: skip
    rec.update(extra)
    return rec


def open_record(source, ext_id, name, lon=76.9, lat=43.2, category="coffee", **extra):
    rec = {
        "source": source, "external_id": ext_id, "lon": lon, "lat": lat, "category": category,
        "name_ru": None, "name_en": None, "name_kk": None, "address_ru": None,
        "address_en": None, "website": None, "phone": None,
    }  # fmt: skip
    rec["name_ru" if any("Ѐ" <= ch <= "ӿ" for ch in name) else "name_en"] = name
    rec.update(extra)
    return rec


def place_row(conn, place_id):
    return q(conn, "SELECT * FROM places WHERE id = %s", (place_id,))[0]


def sources_of(conn, place_id):
    rows = q(conn, "SELECT field, source FROM place_field_sources WHERE place_id = %s", (place_id,))
    return {r["field"]: r["source"] for r in rows}


# ------------------------------------------------------------------------- regions and boundary


def test_kazakhstan_region_exists_and_almaty_stays_default(sconn):
    rows = q(sconn, "SELECT id, is_default, ST_IsValid(boundary) AS ok FROM regions ORDER BY id")
    assert {r["id"]: r["is_default"] for r in rows} == {"almaty": True, "kazakhstan": False}
    assert all(r["ok"] for r in rows)


def test_points_inside_follow_the_boundary_not_the_box(sconn):
    pts = [
        (76.9455, 43.2389),  # Almaty
        (71.43, 51.13),  # Astana
        (68.27, 43.30),  # Turkestan
        (37.62, 55.75),  # Moscow: outside
        (69.24, 41.30),  # Tashkent: inside the box, outside the country
        (46.85, 40.60),  # Naftalan (Azerbaijan): inside the box of the country
    ]
    assert region_mod.points_inside(sconn, "kazakhstan", pts) == [
        True,
        True,
        True,
        False,
        False,
        False,
    ]
    assert region_mod.points_inside(sconn, "almaty", pts[:2]) == [True, False]
    assert region_mod.region_bbox(sconn, "kazakhstan")[0] < 47
    with pytest.raises(region_mod.UnknownRegion):
        region_mod.region_bbox(sconn, "nowhere")


def test_filter_inside_drops_foreign_records(sconn):
    recs = [
        open_record("overture", "a", "Ok", 76.95, 43.25),
        open_record("overture", "b", "No", 69.24, 41.3),
    ]
    kept = region_mod.filter_inside(sconn, "kazakhstan", recs)
    assert [r["external_id"] for r in kept] == ["a"]


# ------------------------------------------------------------------------- field priority


def test_reimport_never_overwrites_manual_partner_or_user_fields(sconn):
    pid, inserted = upsert_place(sconn, osm_record(1, "Кофейня", website="https://osm.example"))
    assert inserted
    assert sources_of(sconn, pid)["name_ru"] == "osm"
    # fields set by hand / user / partner: three different owners
    sconn.execute(
        "UPDATE places SET name_ru = 'Правка', website = 'https://user.example', "
        "address_en = 'Partner street' WHERE id = %s",
        (pid,),
    )
    sconn.execute(
        "INSERT INTO place_field_sources (place_id, field, source) VALUES "
        "(%s, 'name_ru', 'manual'), (%s, 'website', 'user'), (%s, 'address_en', 'partner') "
        "ON CONFLICT (place_id, field) DO UPDATE SET source = EXCLUDED.source",
        (pid, pid, pid),
    )
    # the monthly import brings new values for all three and a new phone
    again, inserted = upsert_place(
        sconn,
        osm_record(
            1, "Новое имя OSM", website="https://new.example", address_en="OSM street", phone="+7 1"
        ),
    )
    assert again == pid and not inserted
    row = place_row(sconn, pid)
    assert row["name_ru"] == "Правка"
    assert row["website"] == "https://user.example"
    assert row["address_en"] == "Partner street"
    assert row["phone"] == "+7 1"  # an open-data field is refreshed
    assert sources_of(sconn, pid) == {
        "name_ru": "manual", "website": "user", "address_en": "partner", "phone": "osm",
        "category_id": "osm", "geom": "osm",
    }  # fmt: skip


def test_manual_override_still_protects_and_is_not_marked_osm(sconn):
    pid, _ = upsert_place(sconn, osm_record(2, "Старое"))
    sconn.execute(
        "UPDATE places SET name_ru = 'Ручное', manual_override = '[\"name_ru\"]' WHERE id = %s",
        (pid,),
    )
    upsert_place(sconn, osm_record(2, "Новое"))
    assert place_row(sconn, pid)["name_ru"] == "Ручное"


def test_hours_of_a_protected_source_are_kept(sconn):
    from datetime import time

    pid, _ = upsert_place(sconn, osm_record(3, "С часами"), [(0, time(9), time(18))])
    assert sources_of(sconn, pid)["hours"] == "osm"
    sconn.execute(
        "UPDATE place_field_sources SET source = 'partner' WHERE place_id = %s AND field = 'hours'",
        (pid,),
    )
    upsert_place(sconn, osm_record(3, "С часами"), [(1, time(10), time(20))])
    hours = q(sconn, "SELECT weekday FROM place_hours WHERE place_id = %s", (pid,))
    assert [h["weekday"] for h in hours] == [0]


def test_open_sources_rank_osm_over_overture_over_foursquare(sconn):
    pid, _ = upsert_place(sconn, osm_record(4, "Рассвет"))
    assert (
        load.import_record(
            sconn, open_record("overture", "o1", "Рассвет", 76.9001, 43.2, phone="+7 2")
        )
        == "linked"
    )
    row = place_row(sconn, pid)
    assert row["phone"] == "+7 2"  # filled a hole
    assert sources_of(sconn, pid)["phone"] == "overture"
    # a lower source does not replace it, a higher one does
    fsq = open_record("foursquare", "f1", "Рассвет", 76.9002, 43.2, phone="+7 3")
    assert load.import_record(sconn, fsq) == "linked"
    assert place_row(sconn, pid)["phone"] == "+7 2"
    upsert_place(sconn, osm_record(4, "Рассвет", phone="+7 4"))
    assert place_row(sconn, pid)["phone"] == "+7 4" and sources_of(sconn, pid)["phone"] == "osm"
    # the OSM name is never replaced by Overture, whatever it says
    load.import_record(sconn, open_record("overture", "o1", "Другое имя", 76.9001, 43.2))
    assert place_row(sconn, pid)["name_ru"] == "Рассвет"


def test_overture_refresh_updates_its_own_fields_but_not_user_edits(sconn):
    rec = open_record(
        "overture", "o9", "Чайхана Навруз", 77.0, 43.3, category="cafe_oriental", phone="+7 10"
    )
    count_before = q(sconn, "SELECT count(*) AS n FROM places")[0]["n"]
    assert load.import_record(sconn, rec) == "inserted"
    pid = q(sconn, "SELECT place_id FROM place_external_ids WHERE external_id = 'o9'")[0][
        "place_id"
    ]
    assert sources_of(sconn, pid)["phone"] == "overture"
    sconn.execute("UPDATE places SET name_ru = 'Навруз (правка)' WHERE id = %s", (pid,))
    sconn.execute(
        "INSERT INTO place_field_sources (place_id, field, source) VALUES (%s, 'name_ru', 'user') "
        "ON CONFLICT (place_id, field) DO UPDATE SET source = 'user'",
        (pid,),
    )
    again = dict(rec, phone="+7 11", website="https://n.example")
    again["name_ru"] = "Чайхана Навруз 2"
    assert load.import_record(sconn, again) == "updated"
    row = place_row(sconn, pid)
    assert row["name_ru"] == "Навруз (правка)"  # the user keeps it
    assert row["phone"] == "+7 11" and row["website"] == "https://n.example"
    assert q(sconn, "SELECT count(*) AS n FROM places")[0]["n"] == count_before + 1  # no new row


# ------------------------------------------------------------------------- merging sources


def test_osm_overture_foursquare_of_one_cafe_become_one_place(sconn):
    pid, _ = upsert_place(sconn, osm_record(10, "Кофе Достык"))
    before = q(sconn, "SELECT count(*) AS n FROM places")[0]["n"]
    o = open_record("overture", "ov-1", "Dostyk Coffee", 76.90015, 43.20005, address_en="Abay 1")
    f = open_record("foursquare", "fs-1", "Кофе Достык", 76.9002, 43.2001, phone="+7 5")
    far = open_record("overture", "ov-2", "Кофе Достык", 76.95, 43.25)  # another branch
    other = open_record("foursquare", "fs-2", "Dostyk Hotel", 76.9001, 43.2, category="hotel")
    assert load.import_record(sconn, o) == "linked"
    assert load.import_record(sconn, f) == "linked"
    assert load.import_record(sconn, far) == "inserted"
    assert load.import_record(sconn, other) == "inserted"
    assert q(sconn, "SELECT count(*) AS n FROM places")[0]["n"] == before + 2
    ids = q(
        sconn,
        "SELECT source, external_id FROM place_external_ids WHERE place_id = %s ORDER BY 1",
        (pid,),
    )
    assert [(r["source"], r["external_id"]) for r in ids] == [
        ("foursquare", "fs-1"),
        ("overture", "ov-1"),
    ]
    row = place_row(sconn, pid)
    assert row["address_en"] == "Abay 1" and row["phone"] == "+7 5"
    # a repeated run finds the same places by their ids
    assert load.import_record(sconn, o) == "updated" and load.import_record(sconn, f) == "updated"
    assert q(sconn, "SELECT count(*) AS n FROM places")[0]["n"] == before + 2


def test_cross_dedupe_folds_rows_created_before_the_osm_import(sconn):
    """Overture came first (own row), OSM later: the pass merges them, OSM row survives."""
    o = open_record("overture", "ov-7", "Бар Чехов", 76.9101, 43.2101, category="bar", phone="+7 7")
    load.import_record(sconn, o)
    pid, _ = upsert_place(sconn, osm_record(70, "Чехов бар", 76.9102, 43.2101, category="bar"))
    ov_id = q(sconn, "SELECT place_id FROM place_external_ids WHERE external_id = 'ov-7'")[0][
        "place_id"
    ]
    assert ov_id != pid
    sconn.execute("INSERT INTO place_photos (place_id, storage_key) VALUES (%s, 'k-ov')", (ov_id,))
    sconn.execute("UPDATE places SET website = 'https://user.example' WHERE id = %s", (ov_id,))
    sconn.execute(
        "INSERT INTO place_field_sources (place_id, field, source) VALUES (%s, 'website', 'user') "
        "ON CONFLICT (place_id, field) DO UPDATE SET source = 'user'",
        (ov_id,),
    )
    stats = load.cross_dedupe(sconn, "kazakhstan")
    assert stats["merged"] == 1
    assert q(sconn, "SELECT 1 FROM places WHERE id = %s", (ov_id,)) == []
    row = place_row(sconn, pid)
    assert row["phone"] == "+7 7" and row["website"] == "https://user.example"
    src = sources_of(sconn, pid)
    assert src["name_ru"] == "osm" and src["website"] == "user" and src["phone"] == "overture"
    ext = q(sconn, "SELECT place_id FROM place_external_ids WHERE external_id = 'ov-7'")
    assert [e["place_id"] for e in ext] == [pid]
    photos = q(sconn, "SELECT place_id FROM place_photos WHERE storage_key = 'k-ov'")
    assert [p["place_id"] for p in photos] == [pid]
    assert load.cross_dedupe(sconn, "kazakhstan")["merged"] == 0  # idempotent
    # the next import of the same Overture record finds the surviving place by id
    assert load.import_record(sconn, o) == "updated"


def test_merge_place_moves_ids_and_sources_and_user_field_takes_over(sconn):
    a, _ = upsert_place(sconn, osm_record(80, "Основа"))
    b = q(
        sconn,
        "INSERT INTO places (name_ru, name_en, geom) VALUES ('Дубль', 'Twin', "
        "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
    )[0]["id"]
    sconn.execute(
        "INSERT INTO place_external_ids (source, external_id, place_id) "
        "VALUES ('foursquare', 'm1', %s)",
        (b,),
    )
    sconn.execute(
        "INSERT INTO place_field_sources (place_id, field, source) VALUES (%s, 'name_ru', 'user'), "
        "(%s, 'name_en', 'overture')",
        (b, b),
    )
    merge_place(sconn, a, b)
    row = place_row(sconn, a)
    assert row["name_ru"] == "Дубль"  # the user's name beats the open-data one
    assert row["name_en"] == "Twin"
    assert (
        sources_of(sconn, a)["name_ru"] == "user" and sources_of(sconn, a)["name_en"] == "overture"
    )
    assert (
        q(sconn, "SELECT place_id FROM place_external_ids WHERE external_id = 'm1'")[0]["place_id"]
        == a
    )


def test_popular_import_marks_curated_fields_manual(sconn):
    import import_popular

    import_popular.import_csv(sconn, ROOT / "data" / "seed" / "popular_places.csv")
    pid = q(sconn, "SELECT id FROM places WHERE manual_override @> '\"name_ru\"' LIMIT 1")[0]["id"]
    assert sources_of(sconn, pid)["name_ru"] == "manual"


# ------------------------------------------------------------------------- pure matching


def test_name_matching_translit_and_generic_words():
    assert match.name_key("Кафе «Достык»") == match.name_key("Dostyk Cafe")
    assert match.name_keys(["Старбакс", None]) == match.name_keys(["Starbaks"])
    a, b = match.name_keys(["Бар Чехов"]), match.name_keys(["Chekhov"])
    assert match.names_similar(a, b)
    assert not match.names_similar(match.name_keys(["Нур"]), match.name_keys(["Алтын Орда"]))


def test_same_place_needs_distance_category_and_name():
    n = match.name_keys(["Старбакс"])
    assert match.same_place(n, "coffee", n, "cafe_european", 20)  # both food
    assert not match.same_place(n, "coffee", n, "hotel", 20)
    assert not match.same_place(n, "coffee", n, "coffee", 500)
    assert match.same_place(n, "park", n, "garden", 300)  # green: wider radius
    assert match.same_place(n, None, n, "coffee", 10)  # unknown category matches
    assert not match.same_place(set(), "coffee", n, "coffee", 1)


# ------------------------------------------------------------------------- Parquet readers


def _write_overture(path):
    import duckdb

    def row(pid, lon, lat, name, hierarchy, conf, status, addr, site, phone):
        return (
            f"SELECT '{pid}' AS id, {lon}::DOUBLE AS lon, {lat}::DOUBLE AS lat, "
            f"{{'primary': '{name}'}} AS names, "
            f"{{'primary': '{hierarchy[-1]}', 'hierarchy': {hierarchy}::VARCHAR[], "
            f"'alternates': NULL::VARCHAR[]}} AS taxonomy, {conf}::DOUBLE AS confidence, "
            f"{status} AS operating_status, "
            f"[{{'freeform': '{addr}', 'locality': 'x'}}] AS addresses, "
            f"['{site}'] AS websites, ['{phone}'] AS phones"
        )

    sql = " UNION ALL ".join(
        [
            row(
                "o1",
                76.9,
                43.2,
                "Dostyk Coffee",
                ["food_and_drink", "cafe", "coffee_shop"],
                0.9,
                "'open'",
                "ул. Абая 1",
                "https://d.kz",
                "+7 700",
            ),
            row("o2", 76.9, 43.2, "Low", ["food_and_drink", "cafe"], 0.2, "'open'", "a", "b", "c"),
            row(
                "o3",
                76.9,
                43.2,
                "Closed",
                ["food_and_drink", "cafe"],
                0.9,
                "'closed'",
                "a",
                "b",
                "c",
            ),
            row(
                "o4",
                76.9,
                43.2,
                "Shop",
                ["shopping", "clothing_store"],
                0.9,
                "'open'",
                "a",
                "b",
                "c",
            ),
            row(
                "o5",
                77.0,
                43.3,
                "Музей Кастеева",
                ["arts_and_entertainment", "museum", "art_museum"],
                0.8,
                "NULL::VARCHAR",
                "Байзакова",
                "x",
                "y",
            ),
        ]
    )
    con = duckdb.connect()
    con.execute(f"COPY ({sql}) TO '{path}' (FORMAT parquet)")
    con.close()


def test_read_overture_maps_filters_and_names(tmp_path):
    path = tmp_path / "overture.parquet"
    _write_overture(path)
    recs = {r["external_id"]: r for r in open_sources.read_overture(path)}
    assert set(recs) == {"o1", "o5"}  # low confidence, closed and unmapped are skipped
    assert recs["o1"]["category"] == "coffee" and recs["o1"]["name_en"] == "Dostyk Coffee"
    assert recs["o1"]["address_ru"] == "ул. Абая 1" and recs["o1"]["phone"] == "+7 700"
    assert recs["o5"]["category"] == "museum" and recs["o5"]["name_ru"] == "Музей Кастеева"
    assert recs["o1"]["source"] == "overture"


def test_read_foursquare_maps_labels_and_skips_closed(tmp_path):
    import duckdb

    path = tmp_path / "fsq.parquet"
    con = duckdb.connect()
    cats = "['Dining and Drinking > Restaurant > Central Asian Restaurant']"
    rows = [
        f"('f1', 'Чайхана', 43.2, 76.9, {cats}, NULL, 'Абая 2', '+7 1', 'https://c.kz')",
        "('f2', 'Old', 43.2, 76.9, ['Dining and Drinking > Cafe'], '2024-01-01', NULL, NULL, NULL)",
        "('f3', 'Barber', 43.2, 76.9, ['Business and Professional Services > Barbershop'],"
        " NULL, NULL, NULL, NULL)",
    ]
    columns = "fsq_place_id, name, latitude, longitude, fsq_category_labels, date_closed"
    con.execute(
        f"COPY (SELECT * FROM (VALUES {', '.join(rows)}) t({columns}, address, tel, website))"
        f" TO '{path}' (FORMAT parquet)"
    )
    con.close()
    recs = list(open_sources.read_foursquare(path))
    assert [r["external_id"] for r in recs] == ["f1"]
    assert recs[0]["category"] == "cafe_oriental" and recs[0]["source"] == "foursquare"
    assert recs[0]["phone"] == "+7 1" and recs[0]["address_ru"] == "Абая 2"


# ------------------------------------------------------------------------- coverage report


def test_coverage_report_counts_categories_sources_and_fields(sconn):
    from datetime import time

    pid, _ = upsert_place(
        sconn, osm_record(90, "Кофейня-90", website="https://w.example"), [(0, time(9), time(18))]
    )
    load.import_record(
        sconn, open_record("overture", "ov-90", "Кофейня 90", 76.9001, 43.2, phone="+7 9")
    )
    load.import_record(
        sconn, open_record("foursquare", "fs-91", "Lonely Hotel", 71.4, 51.1, category="hotel")
    )
    # a point outside every region is not counted
    load.insert_record(sconn, open_record("overture", "ov-out", "Moscow Cafe", 37.6, 55.7))
    sconn.execute("UPDATE places SET avg_check_kzt = 2500 WHERE id = %s", (pid,))
    sconn.execute("INSERT INTO place_photos (place_id, storage_key) VALUES (%s, 'k')", (pid,))
    text = coverage.build_report(sconn, "kazakhstan")
    assert text.startswith("# Покрытие данными мест: Казахстан (kazakhstan)")
    coffee = next(ln for ln in text.splitlines() if ln.startswith("| coffee |"))
    cells = [c.strip() for c in coffee.strip("|").split("|")]
    assert cells[1].isdigit() and int(cells[1]) >= 1
    assert "1 (" in cells[2] or int(cells[2].split()[0]) >= 1  # hours
    assert "| hotel | 1 |" in text
    assert "Moscow" not in text
    assert "| osm |" in text and "| overture |" in text and "| foursquare |" in text
    assert "склеенных из двух и более источников: 1." in text
    assert "| phone | overture |" in text
    almaty = coverage.build_report(sconn, "almaty")
    assert "| hotel |" not in almaty or "| hotel | 1 |" not in almaty  # Astana hotel is not Almaty
