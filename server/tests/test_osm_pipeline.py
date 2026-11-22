"""End-to-end OSM import on a tiny .osm XML fixture: relations, outer-member ways, duplicates."""

from pathlib import Path

import import_places
import psycopg
import pytest
from dedupe import dedupe, distance_m, normalize_name
from import_places import collect, load
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "osm" / "dedupe.osm"
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


def keys(sconn):
    rows = q(sconn, "SELECT osm_type, osm_id FROM places")
    return {(r["osm_type"], r["osm_id"]) for r in rows}


def test_collect_drops_outer_way_and_duplicate_node():
    records, drops, counts = collect(FIXTURE)
    assert counts == {"outer_member": 1, "same_venue": 1}
    assert drops == {("way", 200): ("relation", 500), ("node", 2): ("way", 300)}
    kept = {(r[0], r[1]) for r in records}
    assert kept == {
        ("node", 1),
        ("way", 100),
        ("relation", 500),
        ("way", 300),
        ("node", 3),
        ("node", 4),
        ("node", 5),
        ("node", 6),
    }


def test_load_into_db_and_idempotent(sconn):
    records, drops, _ = collect(FIXTURE)
    stats = load(sconn, records, drops)
    assert stats["inserted"] == 8 and stats["merged"] == 0
    assert keys(sconn) == {(r[0], r[1]) for r in records}

    park = q(
        sconn,
        "SELECT name_ru, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon "
        "FROM places WHERE osm_type='relation' AND osm_id=500",
    )[0]
    assert park["name_ru"] == "Фикстур парк"
    assert 43.22 < park["lat"] < 43.224 and 76.91 < park["lon"] < 76.915  # inside the polygon

    # the surviving way got the node's website and keeps its own hours
    grill = q(
        sconn,
        "SELECT p.website, (SELECT count(*) FROM place_hours h WHERE h.place_id = p.id) AS hrs "
        "FROM places p WHERE osm_type='way' AND osm_id=300",
    )[0]
    assert grill["website"] == "https://dup.example" and grill["hrs"] == 7

    again = load(sconn, records, drops)
    assert again["inserted"] == 0 and again["merged"] == 0 and len(keys(sconn)) == 8


def test_preexisting_duplicate_rows_are_merged_without_losing_data(sconn):
    """Rows imported before the dedupe rules existed are folded into the survivor."""
    records, drops, _ = collect(FIXTURE)
    load(sconn, records, {})  # an old import that had no dedupe rules ...
    for otype, oid in drops:  # ... also left the duplicate objects behind
        sconn.execute(
            "INSERT INTO places (osm_type, osm_id, name_ru, name_en, description_en, geom, "
            "manual_override, typical_visit_min) VALUES (%s, %s, 'Старый дубль', 'Old', 'curated', "
            "ST_SetSRID(ST_MakePoint(76.91, 43.22), 4326)::geography, "
            '\'["description_en", "typical_visit_min"]\'::jsonb, 45)',
            (otype, oid),
        )
    dup_row = q(sconn, "SELECT id FROM places WHERE osm_type='node' AND osm_id=2")[0]["id"]
    sconn.execute("INSERT INTO place_photos (place_id, storage_key) VALUES (%s, 'k1')", (dup_row,))
    stats = load(sconn, records, drops)
    assert stats["merged"] == 2
    assert keys(sconn) == {(r[0], r[1]) for r in records}
    grill = q(
        sconn,
        "SELECT p.id, p.description_en, p.typical_visit_min, p.manual_override FROM places p "
        "WHERE osm_type='way' AND osm_id=300",
    )[0]
    assert grill["description_en"] == "curated" and grill["typical_visit_min"] == 45
    assert "description_en" in grill["manual_override"]
    photos = q(sconn, "SELECT place_id FROM place_photos")
    assert [p["place_id"] for p in photos] == [grill["id"]]


def test_dedupe_rules_pure():
    tags = {"amenity": "cafe", "name": "Ёлка"}
    recs = [
        ("node", 1, 76.9, 43.2, tags),
        ("node", 2, 76.9003, 43.2, tags),  # ~24 m: duplicate node
        ("node", 3, 76.9009, 43.2, tags),  # ~66 m from node 1: separate branch
        ("way", 9, 76.9, 43.2, {"tourism": "hotel", "name": "елка"}),  # other class
    ]
    kept, drops, _ = dedupe(recs, {})
    assert drops == {("node", 2): ("node", 1)}
    assert len(kept) == 3
    assert normalize_name("  Ёлка!! ") == "елка"
    assert 20 < distance_m(76.9, 43.2, 76.9003, 43.2) < 30


def test_module_exposes_bbox_override():
    assert import_places.in_bbox(76.9, 43.2) and not import_places.in_bbox(0, 0)


def test_merge_moves_trip_rows_to_the_survivor(sconn):
    """TECH_PLAN rule 8: trip_items / trip_lodging_options reference places without cascade."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop, other = place("Оставить"), place("Удалить"), place("Рядом")
    user = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    trips = [
        q(
            sconn,
            "INSERT INTO trips (user_id, brief, start_date, end_date) "
            "VALUES (%s, '{}', '2026-12-05', '2026-12-06') RETURNING id",
            (user,),
        )[0]["id"]
        for _ in range(2)
    ]
    for trip in trips:
        for ord_, pid in enumerate((drop, other), start=1):
            sconn.execute(
                "INSERT INTO trip_items (trip_id, day, ord, place_id, kind, starts_at, ends_at, "
                "visit_min) VALUES (%s, '2026-12-05', %s, %s, 'activity', "
                "'2026-12-05 10:00+06', '2026-12-05 11:00+06', 60)",
                (trip, ord_, pid),
            )
    lodging = (
        "INSERT INTO trip_lodging_options (trip_id, place_id, rank, price_per_night_kzt, nights, "
        "total_kzt, recommended) VALUES (%s, %s, %s, 5000, 1, 5000, %s)"
    )
    sconn.execute(lodging, (trips[0], drop, 1, True))  # only the dropped place in trip 0
    sconn.execute(lodging, (trips[1], drop, 1, True))  # both places in trip 1 ...
    sconn.execute(lodging, (trips[1], keep, 2, False))  # ... the survivor is not recommended

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT count(*) AS n FROM places WHERE id = %s", (drop,))[0]["n"] == 0
    rows = q(sconn, "SELECT trip_id, place_id FROM trip_items ORDER BY trip_id, ord")
    assert len(rows) == 4 and {r["place_id"] for r in rows} == {keep, other}  # none lost
    options = q(
        sconn,
        "SELECT trip_id, place_id, recommended FROM trip_lodging_options ORDER BY trip_id",
    )
    assert {(o["trip_id"], o["place_id"], o["recommended"]) for o in options} == {
        (trips[0], keep, True),
        (trips[1], keep, True),  # the collision kept one row and the recommendation
    }


def test_merge_moves_live_route_rows_to_the_survivor(sconn):
    """TECH_PLAN rule 8: chat_live_stops / chat_live_alternatives (Ш-54) have no cascade."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop, other = place("Оставить"), place("Удалить"), place("Рядом")
    user = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    chat = q(sconn, "INSERT INTO chats (user_id) VALUES (%s) RETURNING id", (user,))[0]["id"]
    stop = "INSERT INTO chat_live_stops (chat_id, ord, wish, place_id) VALUES (%s, %s, 'w', %s)"
    alt = (
        "INSERT INTO chat_live_alternatives (chat_id, ord, place_id, rank) VALUES (%s, %s, %s, %s)"
    )
    sconn.execute(stop, (chat, 1, drop))  # the stop itself is the dropped place
    sconn.execute(alt, (chat, 1, other, 0))
    sconn.execute(stop, (chat, 2, other))
    sconn.execute(alt, (chat, 2, drop, 0))  # an alternative that moves
    sconn.execute(alt, (chat, 2, keep, 1))  # ... next to the survivor: one row stays
    sconn.execute(stop, (chat, 3, keep))
    sconn.execute(alt, (chat, 3, drop, 0))  # would duplicate the stop after the move: dropped

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT count(*) AS n FROM places WHERE id = %s", (drop,))[0]["n"] == 0
    stops = q(sconn, "SELECT ord, place_id FROM chat_live_stops ORDER BY ord")
    assert [(r["ord"], r["place_id"]) for r in stops] == [(1, keep), (2, other), (3, keep)]
    alts = q(sconn, "SELECT ord, place_id FROM chat_live_alternatives ORDER BY ord, place_id")
    assert {(r["ord"], r["place_id"]) for r in alts} == {(1, other), (2, keep)}


def test_merge_moves_user_place_signals_to_the_survivor(sconn):
    """TECH_PLAN rule 8: user_place_signals (Ш-38) references places without cascade."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop = place("Оставить"), place("Удалить")
    user = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    for pid, signal in ((drop, "removed"), (drop, "replaced"), (keep, "removed")):
        sconn.execute(
            "INSERT INTO user_place_signals (user_id, place_id, category_slug, signal) "
            "VALUES (%s, %s, 'museum', %s)",
            (user, pid, signal),
        )

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT count(*) AS n FROM places WHERE id = %s", (drop,))[0]["n"] == 0
    rows = q(sconn, "SELECT place_id FROM user_place_signals")
    assert len(rows) == 3 and {r["place_id"] for r in rows} == {keep}  # none lost


def test_merge_moves_analytics_events_to_the_survivor(sconn):
    """TECH_PLAN rule 8: analytics_events (Ш-50) references places without cascade."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop = place("Оставить"), place("Удалить")
    for pid in (drop, drop, keep):
        sconn.execute(
            "INSERT INTO analytics_events (name, source, place_id, occurred_at) "
            "VALUES ('directions_start', 'client', %s, now())",
            (pid,),
        )

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT count(*) AS n FROM places WHERE id = %s", (drop,))[0]["n"] == 0
    rows = q(sconn, "SELECT place_id FROM analytics_events")
    assert len(rows) == 3 and {r["place_id"] for r in rows} == {keep}  # none lost


def test_merge_moves_trip_change_proposals_to_the_survivor(sconn):
    """TECH_PLAN rule 8: trip_change_proposals (Ш-40) has two place columns, no cascade."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop, other = place("Оставить"), place("Удалить"), place("Другое")
    user = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    trip = q(
        sconn,
        "INSERT INTO trips (user_id, brief, start_date, end_date) "
        "VALUES (%s, '{}', '2026-12-01', '2026-12-03') RETURNING id",
        (user,),
    )[0]["id"]
    sconn.execute(  # the dropped place is the stop...
        "INSERT INTO trip_change_proposals (user_id, trip_id, reason, kind, trip_version, day, "
        "to_day, place_id) "
        "VALUES (%s, %s, 'weather', 'move_day', 1, '2026-12-01', '2026-12-02', %s)",
        (user, trip, drop),
    )
    sconn.execute(  # ...and, in another proposal, the replacement
        "INSERT INTO trip_change_proposals (user_id, trip_id, reason, kind, status, trip_version, "
        "day, place_id, target_place_id) "
        "VALUES (%s, %s, 'weather', 'replace', 'declined', 1, '2026-12-02', %s, %s)",
        (user, trip, other, drop),
    )

    merge_place(sconn, keep, drop)

    rows = q(sconn, "SELECT place_id, target_place_id FROM trip_change_proposals ORDER BY kind")
    assert rows[0]["place_id"] == keep  # move_day
    assert rows[1]["place_id"] == other and rows[1]["target_place_id"] == keep  # replace


def test_merge_moves_user_favorites_to_the_survivor(sconn):
    """TECH_PLAN rule 8: user_favorites (Ш-23b) has no cascade; a duplicate favourite is dropped."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop = place("Оставить"), place("Удалить")
    only_drop, both, only_keep = (
        q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"] for _ in range(3)
    )
    for user, pid in (
        (only_drop, drop),
        (both, drop),
        (both, keep),
        (only_keep, keep),
    ):
        sconn.execute("INSERT INTO user_favorites (user_id, place_id) VALUES (%s, %s)", (user, pid))

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT count(*) AS n FROM places WHERE id = %s", (drop,))[0]["n"] == 0
    rows = q(sconn, "SELECT user_id, place_id FROM user_favorites")
    assert {(r["user_id"], r["place_id"]) for r in rows} == {
        (only_drop, keep),
        (both, keep),
        (only_keep, keep),
    }
    assert len(rows) == 3


def test_merge_moves_submissions_to_the_survivor(sconn):
    """TECH_PLAN rule 8: submissions (Ш-44) has no cascade on place_id; the rows move, none lost."""
    from merge import merge_place

    def place(name):
        return q(
            sconn,
            "INSERT INTO places (name_ru, geom) VALUES (%s, "
            "ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography) RETURNING id",
            (name,),
        )[0]["id"]

    keep, drop = place("Оставить"), place("Удалить")
    user = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    for pid in (drop, drop, keep):  # the same person reviewed both places: no uniqueness to break
        sconn.execute(
            "INSERT INTO submissions (user_id, place_id, type, payload, status) "
            "VALUES (%s, %s, 'review', '{\"rating\": 5}', 'approved')",
            (user, pid),
        )

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT count(*) AS n FROM places WHERE id = %s", (drop,))[0]["n"] == 0
    rows = q(sconn, "SELECT place_id FROM submissions")
    assert [r["place_id"] for r in rows] == [keep] * 3


def test_merge_preserves_bookings_and_combines_partner_links(sconn):
    from merge import merge_place

    places = q(
        sconn,
        "INSERT INTO places (name_ru, geom) SELECT name, ST_GeogFromText('POINT(76.9 43.2)')"
        " FROM unnest(ARRAY['keep', 'drop']) AS name RETURNING id, name_ru",
    )
    ids = {row["name_ru"]: row["id"] for row in places}
    keep, drop = ids["keep"], ids["drop"]
    partner = q(sconn, "INSERT INTO partners(name) VALUES ('Cafe') RETURNING id")[0]["id"]
    second = q(sconn, "INSERT INTO partners(name) VALUES ('Hotel') RETURNING id")[0]["id"]
    for pid, place, kind, ref in (
        (partner, keep, "table", None),
        (partner, drop, "food", "cafe"),
        (second, drop, "room", "hotel"),
    ):
        sconn.execute(
            "INSERT INTO partner_places(partner_id, place_id, kinds, external_ref)"
            " VALUES (%s, %s, %s, %s)",
            (pid, place, [kind], ref),
        )
    user = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    booking = q(
        sconn,
        "INSERT INTO bookings (user_id, place_id, partner_id, kind, status, payload) "
        "VALUES (%s, %s, %s, 'food', 'confirmed', '{}') RETURNING id",
        (user, drop, partner),
    )[0]["id"]

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT place_id FROM bookings WHERE id = %s", (booking,)) == [
        {"place_id": keep}
    ]
    links = q(sconn, "SELECT * FROM partner_places WHERE place_id = %s", (keep,))
    assert {r["external_ref"]: sorted(r["kinds"]) for r in links} == {
        "cafe": ["food", "table"],
        "hotel": ["room"],
    }
    assert not q(sconn, "SELECT id FROM places WHERE id = %s", (drop,))


def test_merge_preserves_crowd_reports_and_removes_obsolete_profile(sconn):
    from merge import merge_place

    keep, drop = [
        r["id"]
        for r in q(
            sconn,
            """
            INSERT INTO places (name_en, geom)
            SELECT name, ST_GeogFromText('POINT(76.9 43.2)') FROM (VALUES ('A'), ('B')) p(name)
            RETURNING id
            """,
        )
    ]
    uid = q(sconn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")[0]["id"]
    for pid in (keep, drop):
        sconn.execute(
            "INSERT INTO place_crowd_reports (user_id, place_id, kind, level, distance_m) "
            "VALUES (%s, %s, 'crowd', 1, 5)",
            (uid, pid),
        )
        sconn.execute(
            "INSERT INTO place_crowd_profile (place_id, weekday, hour, level, samples) "
            "VALUES (%s, 1, 10, 0.5, 1)",
            (pid,),
        )

    merge_place(sconn, keep, drop)

    assert q(sconn, "SELECT place_id FROM place_crowd_reports") == [{"place_id": keep}] * 2
    assert q(sconn, "SELECT place_id FROM place_crowd_profile") == [{"place_id": keep}]
