"""Airport stop seed, service windows and terminal-to-Republic Square regression."""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import import_transit as it
import psycopg
import pytest

from app.routing import FakeRouter, TransitNetwork, ValhallaRouter, find_transit_options
from app.routing.transit import AIRPORT_DAY_RELATION, AIRPORT_NIGHT_RELATION
from tests.test_routing import VALHALLA, needs_valhalla
from tests.test_transit_search import DEV_NET, needs_transit_data

T1_ID = UUID("b2dd4f99-bfcc-4d44-a3d7-9f10b4406fb1")
T2_ID = UUID("1db616e8-b482-4962-ac56-f4ec31918014")
T1 = (43.3460325, 77.011753)
T2 = (43.34745, 77.01127)
REPUBLIC = (43.2386, 76.9456)
DAYTIME = datetime(2026, 11, 21, 7, tzinfo=timezone.utc)  # noon in Almaty


def bus(relation_id, ref, nodes):
    return dict(relation_id=relation_id, kind="bus", tags={"ref": ref}, stop_nodes=nodes)


def airport_routes():
    return [
        bus(AIRPORT_DAY_RELATION, "92", [12844683265, 101]),
        bus(AIRPORT_NIGHT_RELATION, "3", [5698201022, 101]),
        bus(7, "3", [5698201022, 101]),
    ]


def test_manual_stops_link_by_relation_and_anchor_once():
    routes = airport_routes()
    stops = {}
    applied = it.apply_manual_stops(stops, routes, it.DEFAULT_MANUAL_STOPS)
    assert applied["manual_stop_links"] == 4
    assert set(stops) == {T1_ID, T2_ID}
    assert [r["stop_nodes"] for r in routes] == [
        [T2_ID, T1_ID, 101],
        [T2_ID, T1_ID, 5698201022, 101],
        [5698201022, 101],
    ]
    assert not it.apply_manual_stops(stops, routes, it.DEFAULT_MANUAL_STOPS)


def test_missing_anchor_does_not_link_by_route_number():
    route = bus(AIRPORT_NIGHT_RELATION, "3", [101, 102])
    stops = {}
    result = it.apply_manual_stops(stops, [route], it.DEFAULT_MANUAL_STOPS)
    assert result["manual_stop_links_skipped"] == 4
    assert not stops and route["stop_nodes"] == [101, 102]


def test_import_sends_stable_manual_stop_ids():
    stops = {}
    it.apply_manual_stops(stops, airport_routes(), it.DEFAULT_MANUAL_STOPS)
    conn = Mock()
    for _ in range(2):
        conn.execute.side_effect = [
            Mock(**{"fetchone.return_value": (stop_id, True)}) for stop_id in stops
        ]
        it.write_db(conn, stops, [], {})
    assert [call.args for call in conn.execute.call_args_list] == [
        (it.UPSERT_MANUAL_STOP, stop) for _ in range(2) for stop in stops.values()
    ]


def test_manual_stop_rows_survive_reimport(test_db_url):
    routes = airport_routes()
    stops = {
        node: dict(
            osm_id=node, lat=T1[0], lon=T1[1], kind="bus", name_ru=None, name_en=None, name_kk=None
        )
        for node in (101, 5698201022, 12844683265)
    }
    it.apply_manual_stops(stops, routes, it.DEFAULT_MANUAL_STOPS)
    seed = it.load_seed(it.DEFAULT_SEED)
    with psycopg.connect(test_db_url) as conn, conn.transaction(force_rollback=True):
        it.write_db(conn, stops, routes, seed)
        conn.execute(
            "UPDATE transit_stops SET name_en = %s, manual_override = %s WHERE id = %s",
            ("Edited terminal", '["name_en"]', T2_ID),
        )
        it.write_db(conn, stops, routes, seed)
        assert conn.execute(
            "SELECT id, osm_id, name_en FROM transit_stops WHERE id = %s", (T2_ID,)
        ).fetchone() == (T2_ID, None, "Edited terminal")
        assert conn.execute(
            """SELECT r.osm_relation_id FROM transit_routes r
               JOIN transit_route_stops rs ON r.id = rs.route_id
               WHERE rs.stop_id = %s ORDER BY r.osm_relation_id""",
            (T2_ID,),
        ).fetchall() == [(AIRPORT_DAY_RELATION,), (AIRPORT_NIGHT_RELATION,)]


def build_network(stops, routes):
    seed = it.load_seed(it.DEFAULT_SEED)
    stop_rows = [dict(stop, id=str(stop_id)) for stop_id, stop in stops.items()]
    route_rows, stop_links = [], []
    for route in routes:
        relation_id = route["relation_id"]
        route_id, ref, kind = str(relation_id), route["tags"].get("ref"), route["kind"]
        params = it.seed_for(seed, kind, ref)
        route_rows.append(
            dict(
                id=route_id,
                osm_relation_id=relation_id,
                ref=ref,
                kind=kind,
                name_ru=None,
                name_en=None,
                headway=params["avg_headway_min"],
                speed=params["speed_kmh"],
            )
        )
        stop_links.extend(
            dict(route_id=route_id, stop_id=str(stop_id)) for stop_id in route["stop_nodes"]
        )
    return TransitNetwork.build(stop_rows, route_rows, stop_links)


def ride_from_terminal(options, routes_by_id, expected_relation):
    return [
        leg
        for option in options
        for leg in option.legs
        if leg.type == "ride"
        and leg.from_point in (T1, T2)
        and routes_by_id[leg.route_id] == expected_relation
    ]


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (5, 59, AIRPORT_NIGHT_RELATION),
        (6, 0, AIRPORT_DAY_RELATION),
        (22, 59, AIRPORT_DAY_RELATION),
        (23, 0, AIRPORT_NIGHT_RELATION),
    ],
)
def test_terminal_to_republic_service_windows(hour, minute, expected):
    routes = airport_routes()
    stops = {
        101: dict(
            lat=REPUBLIC[0], lon=REPUBLIC[1], kind="bus", name_ru=None, name_en=None, name_kk=None
        ),
        5698201022: dict(
            lat=43.3463823, lon=77.0072253, kind="bus", name_ru=None, name_en=None, name_kk=None
        ),
    }
    it.apply_manual_stops(stops, routes, it.DEFAULT_MANUAL_STOPS)
    network = build_network(stops, routes)
    options = asyncio.run(
        find_transit_options(
            network,
            FakeRouter(),
            T2,
            REPUBLIC,
            datetime(2026, 11, 21, hour, minute),
        )
    )
    relations = {r.id: r.osm_relation_id for r in network.routes}
    assert ride_from_terminal(options, relations, expected)
    other = AIRPORT_DAY_RELATION if expected == AIRPORT_NIGHT_RELATION else AIRPORT_NIGHT_RELATION
    assert not ride_from_terminal(options, relations, other)


def test_airport_real_pbf():
    pbf = os.environ.get("JOL_TEST_AIRPORT_PBF")
    if not pbf:
        pytest.skip("set JOL_TEST_AIRPORT_PBF to verify airport stops on the real OSM extract")
    relations, nodes, ways = it.extract(pbf)
    stops, routes, _ = it.build_network(relations, nodes, ways)
    assert it.apply_manual_stops(stops, routes, it.DEFAULT_MANUAL_STOPS)["manual_stop_links"] == 4
    del relations, nodes, ways
    network = build_network(stops, routes)
    for terminal in (T1, T2):
        options = asyncio.run(
            find_transit_options(network, FakeRouter(), terminal, REPUBLIC, DAYTIME)
        )
        assert ride_from_terminal(
            options, {r.id: r.osm_relation_id for r in network.routes}, AIRPORT_DAY_RELATION
        )


@needs_valhalla
@needs_transit_data
@pytest.mark.parametrize("terminal", [T1, T2])
def test_airport_real_valhalla(terminal):
    async def find():
        router = ValhallaRouter(VALHALLA)
        try:
            return await find_transit_options(DEV_NET, router, terminal, REPUBLIC, DAYTIME)
        finally:
            await router.aclose()

    assert ride_from_terminal(
        asyncio.run(find()), {r.id: r.osm_relation_id for r in DEV_NET.routes}, AIRPORT_DAY_RELATION
    )
