"""Transit import (data/osm/import_transit.py) on a tiny .osm fixture + idempotent DB upsert."""

from pathlib import Path

import import_transit as it
import psycopg
import pytest
from psycopg.rows import dict_row

FIXTURE = Path(__file__).parent / "fixtures" / "osm" / "transit.osm"


@pytest.fixture(scope="module")
def network():
    relations, nodes, ways = it.extract(str(FIXTURE))
    stops, routes, stats = it.build_network(relations, nodes, ways)
    return stops, routes, stats


def by_rel(routes):
    return {r["relation_id"]: r for r in routes}


def test_extract_counts_relations_and_ways():
    relations, nodes, ways = it.extract(str(FIXTURE))
    assert set(relations) == {9001, 9002, 9010, 9020, 9030}
    assert set(ways) == {800, 801}
    assert relations[9001]["kind"] == "metro"


def test_metro_directions_share_stations(network):
    stops, routes, stats = network
    r = by_rel(routes)
    fwd = [stops[n]["name_ru"] for n in r[9001]["stop_nodes"]]
    back = [stops[n]["name_ru"] for n in r[9002]["stop_nodes"]]
    assert fwd == ["Alpha", "Beta", "Gamma"] and back == ["Gamma", "Beta", "Alpha"]
    # one station object per name, shared by both directions
    assert set(r[9001]["stop_nodes"]) == set(r[9002]["stop_nodes"])
    assert stats["metro_directions_merged"] == 3
    assert {stops[n]["kind"] for n in r[9001]["stop_nodes"]} == {"metro"}
    assert stops[r[9001]["stop_nodes"][1]]["name_en"] == "Beta EN"


def test_stop_and_platform_are_one_stop(network):
    stops, routes, stats = network
    seq = by_rel(routes)[9010]["stop_nodes"]
    assert [stops[n]["name_ru"] for n in seq] == ["Mall", "Park"]
    assert seq == [12, 14]  # platforms win, stop_positions are folded into them
    assert stats["stop_platform_folded"] == 2


def test_short_relation_skipped(network):
    _, routes, stats = network
    assert 9020 not in by_rel(routes)
    assert stats["routes_skipped_lt2_stops"] == 1


def test_unordered_relation_is_reordered_along_way_geometry(network):
    stops, routes, stats = network
    seq = by_rel(routes)[9030]["stop_nodes"]
    assert [stops[n]["name_ru"] for n in seq] == ["S0", "S1", "S2", "S3", "S4", "S5"]
    assert stats["routes_reordered_by_geometry"] == 1


def test_zigzag_ratio_orders():
    relations, nodes, _ = it.extract(str(FIXTURE))
    assert it.zigzag_ratio([31, 32, 33, 34, 35, 36], nodes) == pytest.approx(1.0, abs=0.01)
    assert it.zigzag_ratio([31, 36, 32, 35, 33, 34], nodes) > 2.5


def test_interval_parsing():
    assert it.parse_interval("12") == 12
    assert it.parse_interval("00:15") == 15
    assert it.parse_interval("0:00:30") is None  # 0.5 min: implausible
    assert it.parse_interval("irregular") is None
    assert it.parse_interval(None) is None


def test_seed_has_defaults_for_every_kind():
    seed = it.load_seed(it.DEFAULT_SEED)
    for kind in ("metro", "bus", "trolleybus", "tram"):
        s = it.seed_for(seed, kind, "999")
        assert s["avg_headway_min"] > 0 and s["speed_kmh"] > 0


# --- database -------------------------------------------------------------------------------


@pytest.fixture
def sconn(test_db_url):
    with psycopg.connect(test_db_url) as c:
        yield c
        c.rollback()


def rows(conn, query, params=None):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def test_write_db_idempotent_with_manual_override_and_stale_cleanup(sconn, network):
    stops, routes, _ = network
    seed = it.load_seed(it.DEFAULT_SEED)

    c1 = it.write_db(sconn, stops, routes, seed)
    assert c1["routes_inserted"] == len(routes) and c1["stops_inserted"] == len(stops)
    n_rs = rows(sconn, "SELECT count(*) AS n FROM transit_route_stops")[0]["n"]
    assert n_rs == sum(len(r["stop_nodes"]) for r in routes)

    # headways: seed default for metro, OSM interval for bus 10, kind default for bus 30
    hw = {
        r["osm_relation_id"]: float(r["avg_headway_min"])
        for r in rows(sconn, "SELECT osm_relation_id, avg_headway_min FROM transit_routes")
    }
    assert hw[9001] == 8.0 and hw[9010] == 12.0 and hw[9030] == 15.0

    c2 = it.write_db(sconn, stops, routes, seed)
    assert c2["routes_updated"] == len(routes) and c2["stops_updated"] == len(stops)
    assert c2["routes_inserted"] == 0 and c2["stops_inserted"] == 0
    assert rows(sconn, "SELECT count(*) AS n FROM transit_route_stops")[0]["n"] == n_rs

    # a hand-edited headway survives a re-import
    sconn.execute(
        "UPDATE transit_routes SET avg_headway_min = 5, manual_override = '[\"avg_headway_min\"]' "
        "WHERE osm_relation_id = 9010"
    )
    it.write_db(sconn, stops, routes, seed)
    got = rows(sconn, "SELECT avg_headway_min FROM transit_routes WHERE osm_relation_id = 9010")
    assert float(got[0]["avg_headway_min"]) == 5.0

    # a route that disappeared from OSM is removed together with its orphan stops
    kept = [r for r in routes if r["relation_id"] != 9030]
    c3 = it.write_db(sconn, stops, kept, seed)
    assert c3["routes_deleted_stale"] == 1 and c3["stops_deleted_orphan"] >= 6
    assert not rows(sconn, "SELECT 1 FROM transit_routes WHERE osm_relation_id = 9030")


def test_empty_extract_does_not_wipe_network(sconn, network):
    stops, routes, _ = network
    seed = it.load_seed(it.DEFAULT_SEED)
    it.write_db(sconn, stops, routes, seed)
    it.write_db(sconn, {}, [], seed)
    assert rows(sconn, "SELECT count(*) AS n FROM transit_routes")[0]["n"] == len(routes)


def test_migration_constraints(sconn):
    with pytest.raises(psycopg.errors.CheckViolation):
        sconn.execute(
            "INSERT INTO transit_routes (kind, avg_headway_min, speed_kmh) VALUES ('bus', 0, 10)"
        )
