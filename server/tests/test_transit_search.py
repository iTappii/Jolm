"""Transit search (Ш-21): synthetic network + FakeRouter; reference pairs against the dev data."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from app.config import get_settings
from app.routing import FakeRouter, TransitNetwork, ValhallaRouter, find_transit_options
from app.routing.fake import haversine_m
from app.routing.transit import TRANSFER_BUFFER_S, hop_speed_boost
from tests.test_routing import VALHALLA, needs_valhalla

PAIRS = json.loads((Path(__file__).parent / "fixtures/transit/reference_pairs.json").read_text())


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# --- synthetic network --------------------------------------------------------------------
# Bus 1 (east-west along lat 43.25): S0..S4, 815 m apart. Bus 2 (north-south through S2's area):
# T0 north, T1 ~100 m from S2 (transfer by walking), T2 south. Metro M (far away, own line).

LAT0, LON0, DLON = 43.25, 76.90, 0.010


def stop_row(i, lat, lon, kind="bus", name=None):
    return dict(
        id="s%d" % i,
        lat=lat,
        lon=lon,
        name_ru=name or "Stop %d" % i,
        name_en=None,
        name_kk=None,
        kind=kind,
    )


def build(headway1=10.0, headway2=20.0, with_metro=True):
    stops = [stop_row(i, LAT0, LON0 + DLON * i) for i in range(5)]  # s0..s4 on bus 1
    stops += [
        stop_row(10, LAT0 + 0.02, LON0 + 2 * DLON + 0.001),  # t0
        stop_row(11, LAT0 + 0.0005, LON0 + 2 * DLON + 0.0012),  # t1 ~ 100 m from s2
        stop_row(12, LAT0 - 0.02, LON0 + 2 * DLON + 0.001),  # t2
    ]
    routes = [
        dict(
            id="r1", kind="bus", ref="1", name_ru=None, name_en=None, headway=headway1, speed=20.0
        ),
        dict(
            id="r2", kind="bus", ref="2", name_ru=None, name_en=None, headway=headway2, speed=20.0
        ),
    ]
    rs = [dict(route_id="r1", stop_id="s%d" % i) for i in range(5)]
    rs += [dict(route_id="r2", stop_id=s) for s in ("s10", "s11", "s12")]
    if with_metro:
        stops += [
            stop_row(20, 43.30, 76.80, "metro", "M0"),
            stop_row(21, 43.30, 76.83, "metro", "M1"),
            stop_row(22, 43.30, 76.86, "metro", "M2"),
        ]
        routes.append(
            dict(
                id="rm", kind="metro", ref="1", name_ru=None, name_en=None, headway=8.0, speed=34.0
            )
        )
        rs += [dict(route_id="rm", stop_id=s) for s in ("s20", "s21", "s22")]
    return TransitNetwork.build(stops, routes, rs)


A_NEAR_S0 = (LAT0 + 0.0005, LON0)
B_NEAR_S4 = (LAT0 + 0.0005, LON0 + 4 * DLON)
B_NEAR_T2 = (LAT0 - 0.0205, LON0 + 2 * DLON + 0.001)


def search(net, a, b, **kw):
    return run(find_transit_options(net, FakeRouter(), a, b, **kw))


def test_direct_option_duration_is_walk_wait_ride_walk():
    net = build(with_metro=False)
    opts = search(net, A_NEAR_S0, B_NEAR_S4, drop_slower_than_walking=False)
    best = opts[0]
    assert best.transfers == 0 and best.refs == ["1"] and best.mode == "bus"
    assert best.approximate is True
    assert [leg.type for leg in best.legs] == ["walk", "ride", "walk"]
    ride = best.legs[1]
    assert ride.n_stops == 4 and ride.wait_s == 5 * 60  # half of the 10 min headway
    # ride: 4 hops of ~815 m * 1.2 detour at 20 km/h
    hop = haversine_m((LAT0, LON0), (LAT0, LON0 + DLON)) * 1.2
    assert ride.duration_s - ride.wait_s == pytest.approx(4 * hop / (20 / 3.6), rel=0.01)
    assert best.duration_s == pytest.approx(sum(leg.duration_s for leg in best.legs), abs=0.2)
    assert ride.from_name == "Stop 0" and ride.to_name == "Stop 4" and ride.geometry


def test_one_transfer_via_walk_between_nearby_stops():
    net = build(with_metro=False)
    opts = search(net, A_NEAR_S0, B_NEAR_T2, drop_slower_than_walking=False)
    best = opts[0]
    assert best.transfers == 1 and best.refs == ["1", "2"]
    assert [leg.type for leg in best.legs] == ["walk", "ride", "walk", "ride", "walk"]
    transfer = best.legs[2]
    assert 50 < transfer.distance_m < 250  # ~100 m straight line x detour
    waits = best.legs[1].wait_s + best.legs[3].wait_s
    assert waits == 10 * 30 + 20 * 30
    assert best.duration_s == pytest.approx(
        sum(leg.duration_s for leg in best.legs) + TRANSFER_BUFFER_S, abs=0.2
    )


def test_no_transfer_beyond_radius():
    # same network but bus 2 moved 600 m away from bus 1: no walkable transfer -> no option
    stops = [stop_row(i, LAT0, LON0 + DLON * i) for i in range(5)]
    stops += [
        stop_row(10, LAT0 + 0.02, LON0 + 2 * DLON + 0.008),
        stop_row(12, LAT0 - 0.02, LON0 + 2 * DLON + 0.008),
    ]
    routes = [
        dict(id="r1", kind="bus", ref="1", name_ru=None, name_en=None, headway=10.0, speed=20.0),
        dict(id="r2", kind="bus", ref="2", name_ru=None, name_en=None, headway=10.0, speed=20.0),
    ]
    rs = [dict(route_id="r1", stop_id="s%d" % i) for i in range(5)]
    rs += [dict(route_id="r2", stop_id="s10"), dict(route_id="r2", stop_id="s12")]
    net = TransitNetwork.build(stops, routes, rs)
    assert (
        search(
            net, A_NEAR_S0, (LAT0 - 0.0205, LON0 + 2 * DLON + 0.008), drop_slower_than_walking=False
        )
        == []
    )


def test_single_relation_line_gets_reverse_direction():
    net = build(with_metro=False)
    opts = search(net, B_NEAR_S4, A_NEAR_S0, drop_slower_than_walking=False)
    assert opts and opts[0].transfers == 0 and opts[0].refs == ["1"]
    assert opts[0].legs[1].from_name == "Stop 4"


def test_two_relations_of_a_line_are_not_reversed_again():
    net = build(with_metro=False)
    assert sum(1 for r in net.routes if r.inferred_reverse) == 2  # bus 1 and bus 2, once each
    stops = [stop_row(i, LAT0, LON0 + DLON * i) for i in range(3)]
    routes = [
        dict(id="a", kind="bus", ref="7", name_ru=None, name_en=None, headway=10.0, speed=20.0),
        dict(id="b", kind="bus", ref="7", name_ru=None, name_en=None, headway=10.0, speed=20.0),
    ]
    rs = [dict(route_id="a", stop_id="s%d" % i) for i in range(3)]
    rs += [dict(route_id="b", stop_id="s%d" % i) for i in (2, 1, 0)]
    assert not any(r.inferred_reverse for r in TransitNetwork.build(stops, routes, rs).routes)


def test_metro_tagged_by_primary_vehicle():
    net = build()
    a, b = (43.3005, 76.80), (43.3005, 76.86)
    opts = search(net, a, b, drop_slower_than_walking=False)
    assert opts[0].mode == "metro" and opts[0].kind == "metro" and opts[0].refs == ["1"]
    assert opts[0].to_dict()["mode"] == "metro"


def test_best_of_each_mode_is_kept():
    # a bus line next to the metro one: both modes must be offered
    stops = [
        stop_row(0, 43.30, 76.80),
        stop_row(1, 43.30, 76.86),
        stop_row(20, 43.3002, 76.80, "metro", "M0"),
        stop_row(21, 43.3002, 76.86, "metro", "M1"),
    ]
    routes = [
        dict(id="b", kind="bus", ref="9", name_ru=None, name_en=None, headway=15.0, speed=18.0),
        dict(id="m", kind="metro", ref="1", name_ru=None, name_en=None, headway=8.0, speed=34.0),
    ]
    rs = [
        dict(route_id="b", stop_id="s0"),
        dict(route_id="b", stop_id="s1"),
        dict(route_id="m", stop_id="s20"),
        dict(route_id="m", stop_id="s21"),
    ]
    net = TransitNetwork.build(stops, routes, rs)
    opts = search(
        net, (43.3001, 76.80), (43.3001, 76.86), drop_slower_than_walking=False, max_options=2
    )
    assert {o.mode for o in opts} == {"metro", "bus"}
    assert opts[0].mode == "metro"  # faster, sorted first


def test_dominated_itinerary_not_returned():
    net = build()
    # S0 -> S4 direct on bus 1; "bus 1 + bus 2" must not be offered as an alternative
    opts = search(net, A_NEAR_S0, B_NEAR_S4, drop_slower_than_walking=False, max_options=5)
    assert all(o.refs == ["1"] for o in opts)


def test_service_hours_filter_metro_at_night():
    net = build()
    a, b = (43.3005, 76.80), (43.3005, 76.86)
    night = datetime(2026, 11, 21, 21, 0, tzinfo=timezone.utc)  # 02:00 Almaty
    noon = datetime(2026, 11, 21, 7, 0, tzinfo=timezone.utc)  # 12:00 Almaty
    assert search(net, a, b, depart=night, drop_slower_than_walking=False) == []
    assert search(net, a, b, depart=noon, drop_slower_than_walking=False)[0].mode == "metro"
    early = datetime(2026, 11, 21, 6, 10)  # naive = local; metro opens 06:20, buses 06:00
    assert search(net, A_NEAR_S0, B_NEAR_S4, depart=early, drop_slower_than_walking=False)


def test_nothing_near_returns_empty():
    net = build()
    assert search(net, (43.40, 77.10), B_NEAR_S4) == []


def test_options_slower_than_walking_are_dropped():
    net = build(with_metro=False)
    a, b = (LAT0 + 0.0005, LON0), (LAT0 + 0.0005, LON0 + 0.004)  # ~330 m apart
    assert search(net, a, b) == []


def test_hop_speed_boost():
    assert hop_speed_boost(500) == 1.0
    assert hop_speed_boost(2000) == pytest.approx(1.5)
    assert hop_speed_boost(10_000) == 2.0


async def test_load_from_database_and_search(conn):
    """SQL loading (stops/routes/route_stops) feeds the same search."""
    ids = {}
    for name, lon in (("A", 76.90), ("B", 76.91), ("C", 76.92)):
        row = await (
            await conn.execute(
                "INSERT INTO transit_stops (kind, name_ru, geom) "
                "VALUES ('bus', %s, ST_SetSRID(ST_MakePoint(%s, 43.25), 4326)::geography) "
                "RETURNING id",
                (name, lon),
            )
        ).fetchone()
        ids[name] = row["id"]
    # a stop that belongs to no route must not be loaded
    await conn.execute(
        "INSERT INTO transit_stops (kind, geom) "
        "VALUES ('bus', ST_SetSRID(ST_MakePoint(76.5, 43.2), 4326)::geography)"
    )
    row = await (
        await conn.execute(
            "INSERT INTO transit_routes (kind, ref, avg_headway_min, speed_kmh) "
            "VALUES ('bus', '5', 10, 20) RETURNING id"
        )
    ).fetchone()
    for i, name in enumerate("ABC"):
        await conn.execute(
            "INSERT INTO transit_route_stops (route_id, stop_id, ord) VALUES (%s, %s, %s)",
            (row["id"], ids[name], i),
        )
    net = await TransitNetwork.load(conn)
    assert len(net.stops) == 3 and len(net.routes) == 2  # + inferred reverse direction
    opts = await find_transit_options(
        net, FakeRouter(), (43.2503, 76.8995), (43.2503, 76.9205), drop_slower_than_walking=False
    )
    assert opts[0].refs == ["5"] and opts[0].legs[1].n_stops == 2


# --- reference pairs against the real (dev) data ---------------------------------------------


def _load_dev_network():
    try:
        with psycopg.connect(get_settings().database_url, row_factory=psycopg.rows.dict_row) as c:
            n = c.execute("SELECT count(*) AS n FROM transit_route_stops").fetchone()["n"]
            if not n:
                return None
            return _load(c)
    except Exception:
        return None


def _load(sync_conn):
    # TransitNetwork.load() takes an async connection; reuse its SQL on the sync one
    from app.routing import transit as t

    def fetch(q):
        return sync_conn.execute(q).fetchall()

    return TransitNetwork.build(fetch(t.STOPS_SQL), fetch(t.ROUTES_SQL), fetch(t.ROUTE_STOPS_SQL))


DEV_NET = _load_dev_network()
needs_transit_data = pytest.mark.skipif(
    DEV_NET is None, reason="transit tables empty (make import-transit)"
)


@needs_valhalla
@needs_transit_data
@pytest.mark.parametrize("pair", PAIRS, ids=[p["id"] for p in PAIRS])
def test_reference_pairs_give_sensible_options(pair):
    a, b = tuple(pair["from"]), tuple(pair["to"])

    async def go():
        r = ValhallaRouter(VALHALLA)
        try:
            opts = await find_transit_options(DEV_NET, r, a, b)
            walk = await r.route(a, b, "walk")
            return opts, walk
        finally:
            await r.aclose()

    opts, walk = run(go())
    assert opts, "no transit option for %s" % pair["id"]
    straight = haversine_m(a, b)
    for o in opts:
        assert o.approximate and o.transfers <= 1 and o.refs
        assert o.legs[0].type == "walk" and o.legs[-1].type == "walk"
        assert o.duration_s < walk.duration_s  # otherwise "just walk"
        assert o.duration_s >= straight / (60 / 3.6)  # nothing faster than 60 km/h door to door
        assert o.mode in ("bus", "metro") and o.kind in ("bus", "metro", "trolleybus", "tram")
        assert o.duration_s == pytest.approx(
            sum(leg.duration_s for leg in o.legs) + (TRANSFER_BUFFER_S if o.transfers else 0),
            abs=0.5,
        )
    if "expect_mode" in pair:
        assert opts[0].mode == pair["expect_mode"] and opts[0].transfers == 0
    print(
        pair["id"],
        [(o.mode, round(o.duration_s / 60), o.transfers, o.refs) for o in opts[:2]],
    )
