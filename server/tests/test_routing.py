"""Routing: FakeRouter, Valhalla response parsing (recorded fixtures), client behaviour."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.routing import (
    FakeRouter,
    NoRoute,
    RoutingUnavailable,
    ValhallaRouter,
    make_router,
)
from app.routing.fake import haversine_m
from app.routing.valhalla import COSTING, parse_matrix, parse_route

FIX = Path(__file__).parent / "fixtures" / "valhalla"
REPUBLIC = (43.2381, 76.9453)
MEDEU = (43.1573, 77.0587)
PANFILOV = (43.2587, 76.9457)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# --- FakeRouter ---------------------------------------------------------------------------


def test_fake_route_speeds_and_order():
    f = FakeRouter()
    walk, scooter, car = (run(f.route(REPUBLIC, MEDEU, m)) for m in ("walk", "scooter", "car"))
    assert walk.duration_s > scooter.duration_s > car.duration_s
    assert walk.distance_m >= haversine_m(REPUBLIC, MEDEU)
    assert 4 <= walk.distance_m / walk.duration_s * 3.6 <= 5.5
    assert walk.geometry


def test_fake_matrix_shape_and_diagonal():
    f = FakeRouter()
    pts = [REPUBLIC, MEDEU, PANFILOV]
    m = run(f.matrix(pts, pts, "walk"))
    assert len(m.durations_s) == 3 and len(m.durations_s[0]) == 3
    assert all(m.durations_s[i][i] == 0 for i in range(3))
    assert m.durations_s[0][1] == pytest.approx(m.durations_s[1][0])


def test_fake_unreachable_is_none_and_noroute():
    f = FakeRouter(unreachable_over_m={"walk": 5000})
    m = run(f.matrix([REPUBLIC], [PANFILOV, MEDEU], "walk"))
    assert m.durations_s[0][0] is not None and m.durations_s[0][1] is None
    with pytest.raises(NoRoute):
        run(f.route(REPUBLIC, MEDEU, "walk"))


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        run(FakeRouter().route(REPUBLIC, MEDEU, "bus"))


def test_make_router_without_url_is_fake():
    assert isinstance(make_router(None), FakeRouter)


# --- parsing recorded Valhalla responses --------------------------------------------------


@pytest.mark.parametrize("mode", ["walk", "scooter", "car"])
def test_parse_recorded_route(mode):
    r = parse_route(mode, load("route_republic_medeu_%s.json" % mode))
    assert r.mode == mode
    assert 10_000 < r.distance_m < 25_000
    assert r.duration_s > 0
    assert isinstance(r.geometry, str) and len(r.geometry) > 50
    assert r.maneuvers and r.maneuvers[0].instruction
    # sum of maneuver lengths ~ total distance
    assert sum(m.length_m for m in r.maneuvers) == pytest.approx(r.distance_m, rel=0.01)


def test_recorded_mode_ordering_and_speeds():
    walk, sc, car = (
        parse_route(m, load("route_republic_medeu_%s.json" % m)) for m in ("walk", "scooter", "car")
    )
    assert walk.duration_s > sc.duration_s > car.duration_s
    assert 4.0 <= walk.distance_m / walk.duration_s * 3.6 <= 5.6
    assert 10.0 <= sc.distance_m / sc.duration_s * 3.6 <= 20.0


def test_parse_matrix_4x4():
    m = parse_matrix("walk", load("matrix_walk_4x4.json"), 4, 4)
    assert len(m.durations_s) == 4
    assert all(m.durations_s[i][i] == 0 for i in range(4))
    assert m.durations_s[0][1] > 0 and m.distances_m[0][1] > 0


def test_parse_matrix_null_is_none():
    data = {
        "sources_to_targets": [
            [
                {"from_index": 0, "to_index": 0, "time": 60, "distance": 0.1},
                {"from_index": 0, "to_index": 1, "time": None, "distance": None},
            ]
        ]
    }
    m = parse_matrix("walk", data, 1, 2)
    assert m.durations_s == [[60.0, None]]
    assert m.distances_m == [[100.0, None]]


def test_costing_map_covers_modes():
    assert {k: v["costing"] for k, v in COSTING.items()} == {
        "walk": "pedestrian",
        "scooter": "bicycle",
        "car": "auto",
    }
    assert COSTING["scooter"]["options"]["cycling_speed"] == 15.0


# --- client behaviour with a mock transport -----------------------------------------------


def _router(handler):
    client = httpx.AsyncClient(
        base_url="http://valhalla.test", transport=httpx.MockTransport(handler)
    )
    return ValhallaRouter("http://valhalla.test", client=client, retries=2)


def test_client_route_request_and_parse():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=load("route_republic_medeu_scooter.json"))

    r = run(_router(handler).route(REPUBLIC, MEDEU, "scooter"))
    assert seen["path"] == "/route"
    assert seen["body"]["costing"] == "bicycle"
    assert seen["body"]["costing_options"]["bicycle"]["cycling_speed"] == 15.0
    assert seen["body"]["locations"][0] == {"lat": REPUBLIC[0], "lon": REPUBLIC[1]}
    assert r.mode == "scooter" and r.distance_m > 10_000


def test_client_retries_connect_errors_only():
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json=load("route_republic_medeu_car.json"))

    assert run(_router(flaky).route(REPUBLIC, MEDEU, "car")).mode == "car"
    assert calls["n"] == 3

    calls["n"] = 0

    def timeout(request):
        calls["n"] += 1
        raise httpx.ReadTimeout("slow")

    with pytest.raises(RoutingUnavailable):
        run(_router(timeout).route(REPUBLIC, MEDEU, "car"))
    assert calls["n"] == 1  # no retry on read timeout

    calls["n"] = 0

    def down(request):
        calls["n"] += 1
        raise httpx.ConnectError("refused")

    with pytest.raises(RoutingUnavailable):
        run(_router(down).route(REPUBLIC, MEDEU, "car"))
    assert calls["n"] == 3


def test_client_error_mapping():
    err = load("error_no_route.json")
    with pytest.raises(NoRoute):
        run(_router(lambda r: httpx.Response(400, json=err)).route(REPUBLIC, MEDEU, "car"))
    with pytest.raises(RoutingUnavailable):
        run(_router(lambda r: httpx.Response(500, text="boom")).route(REPUBLIC, MEDEU, "car"))


def test_client_matrix_pairwise_fallback_marks_unreachable():
    err = load("error_no_route.json")
    ok = {"sources_to_targets": [[{"from_index": 0, "to_index": 0, "time": 120, "distance": 0.5}]]}

    def handler(request):
        body = json.loads(request.content)
        if len(body["targets"]) > 1 or body["targets"][0]["lat"] > 50:
            return httpx.Response(400, json=err)
        return httpx.Response(200, json=ok)

    far = (55.0, 66.0)
    m = run(_router(handler).matrix([REPUBLIC], [PANFILOV, far], "walk"))
    assert m.durations_s == [[120.0, None]]
    assert m.distances_m == [[500.0, None]]


# --- integration: only when a real Valhalla is reachable ------------------------------------


def _valhalla_url():
    import os

    url = os.environ.get("VALHALLA_URL")
    if not url:
        try:
            from app.config import get_settings

            url = get_settings().valhalla_url
        except Exception:
            url = None
    if not url:
        return None
    try:
        httpx.get(url.rstrip("/") + "/status", timeout=2.0).raise_for_status()
    except Exception:
        return None
    return url


VALHALLA = _valhalla_url()
needs_valhalla = pytest.mark.skipif(VALHALLA is None, reason="VALHALLA_URL not reachable")

PAIRS = {
    "panfilov_koktobe": (PANFILOV, (43.2465, 76.9588), (1.5, 4.0)),  # distance km range
    "republic_medeu": (REPUBLIC, MEDEU, (12.0, 20.0)),
}


@needs_valhalla
@pytest.mark.parametrize("pair", sorted(PAIRS))
def test_integration_route_three_profiles(pair):
    a, b, (dmin, dmax) = PAIRS[pair]

    async def go():
        r = ValhallaRouter(VALHALLA)
        try:
            return {m: await r.route(a, b, m) for m in ("walk", "scooter", "car")}
        finally:
            await r.aclose()

    res = run(go())
    for m, rr in res.items():
        assert dmin <= rr.distance_m / 1000 <= dmax * 1.5, (m, rr.distance_m)
        print(pair, m, round(rr.duration_s), "s", round(rr.distance_m), "m")
    walk_kmh = res["walk"].distance_m / res["walk"].duration_s * 3.6
    assert 4.0 <= walk_kmh <= 5.6
    assert 10 <= res["scooter"].distance_m / res["scooter"].duration_s * 3.6 <= 20
    assert res["walk"].duration_s > res["scooter"].duration_s > res["car"].duration_s


@needs_valhalla
def test_integration_matrix_and_unreachable():
    async def go():
        r = ValhallaRouter(VALHALLA)
        try:
            pts = [REPUBLIC, MEDEU, PANFILOV]
            m = await r.matrix(pts, pts, "car")
            far = await r.matrix([REPUBLIC], [PANFILOV, (47.5, 66.5)], "walk")
            return m, far
        finally:
            await r.aclose()

    m, far = run(go())
    assert all(m.durations_s[i][i] == 0 for i in range(3))
    assert m.durations_s[0][1] > m.durations_s[0][2] > 0
    assert far.durations_s[0][0] is not None and far.durations_s[0][1] is None
