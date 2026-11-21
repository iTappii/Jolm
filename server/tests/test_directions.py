from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Response
from psycopg import OperationalError

from app import main
from app.db import execute
from app.main import create_app
from app.routing import FakeRouter, NoRoute, RoutingUnavailable, api, service
from app.routing.costs import Tariff
from app.routing.fake import encode_polyline6
from app.routing.geometry import decode_polyline6
from app.routing.transit import TransitLeg, TransitOption
from app.routing.valhalla import ValhallaRouter
from tests.conftest import TransactionalDatabase
from tests.test_places import add_place

ORIGIN = (43.25, 76.95)
TARGET = (43.25, 76.955)
PAYLOAD = {
    "from": {"lat": ORIGIN[0], "lon": ORIGIN[1]},
    "to": {"lat": TARGET[0], "lon": TARGET[1]},
    "depart_at": "2026-11-20T20:30:00Z",
}
TARIFFS = {
    "car": Tariff("car", Decimal(0), Decimal(0), Decimal(75)),
    "taxi": Tariff("taxi", Decimal(500), Decimal(0), Decimal(0)),
    "scooter": Tariff("scooter", Decimal(100), Decimal(30), Decimal(0)),
}


class StubDatabase:
    @asynccontextmanager
    async def transaction(self):
        yield object()


@pytest.fixture
async def directions_api(monkeypatch):
    app = create_app()
    app.state.db = StubDatabase()
    app.state.routing_provider = FakeRouter()
    tariffs = AsyncMock(return_value=TARIFFS.copy())
    monkeypatch.setattr(api, "load_tariffs", tariffs)
    monkeypatch.setattr(api, "get_network", AsyncMock(return_value=object()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield app, client, tariffs


async def test_directions_contract_and_almaty_tariff_date(directions_api):
    _, client, tariffs = directions_api
    response = await client.post("/v1/directions", json=PAYLOAD)
    assert response.status_code == 200, response.text
    tariffs.assert_awaited_once()
    assert tariffs.await_args.args[1] == date(2026, 11, 21)
    options = {option["mode"]: option for option in response.json()}
    assert set(options) == {"walk", "scooter", "taxi", "car"}
    assert [mode for mode, option in options.items() if option["recommended"]] == ["walk"]
    assert all(option["approximate"] for option in options.values())
    assert decode_polyline6(options["walk"]["geometry"]) == [ORIGIN, TARGET]
    assert options["walk"]["cost_kzt_min"] == options["walk"]["cost_kzt_max"] == 0
    assert "duration_s_max" not in options["walk"]
    assert options["taxi"]["cost_kzt_min"] == 500
    assert options["taxi"]["cost_kzt_max"] == 625


@pytest.mark.parametrize(
    "departure,factor",
    [
        ("2026-11-23T02:00:00Z", 1.6),  # Monday, 07:00 in Almaty
        ("2026-11-23T05:00:00Z", 1.25),  # Monday, 10:00 in Almaty
        ("2026-11-22T12:00:00Z", 1.25),  # Sunday, 17:00 in Almaty
    ],
)
async def test_directions_motor_range_for_local_departure(departure, factor, directions_api):
    _, client, _ = directions_api
    response = await client.post("/v1/directions", json={**PAYLOAD, "depart_at": departure})
    assert response.status_code == 200, response.text
    options = {option["mode"]: option for option in response.json()}
    for mode in ("car", "taxi"):
        option = options[mode]
        assert option["duration_s_min"] == option["duration_s"]
        assert option["duration_s_max"] == pytest.approx(option["duration_s"] * factor, abs=0.051)
        assert option["cost_kzt_min"] < option["cost_kzt_max"]
    assert options["taxi"]["cost_kzt_max"] == 500 * factor


@pytest.mark.parametrize(
    "changes",
    [
        {"from": {"lat": 42.99, "lon": 77.0}},
        {"to": {"lat": 43.25, "lon": 77.21}},
        {"to": {"lat": "43.25", "lon": 77.0}},
        {"to": None},
        {"to_place_id": str(uuid4())},
        {"to": None, "to_place_id": "wrong"},
        {"depart_at": "2026-11-20T20:30:00"},
        {"depart_at": 1795293000},
        {"depart_at": "9999-12-31T23:59:59Z"},
    ],
)
async def test_directions_rejects_invalid_input(changes, directions_api):
    _, client, tariffs = directions_api
    response = await client.post("/v1/directions", json={**PAYLOAD, **changes})
    assert response.status_code == 422, response.text
    tariffs.assert_not_awaited()


async def test_directions_partial_engine_failure(directions_api, monkeypatch):
    app, client, _ = directions_api
    actual_route = app.state.routing_provider.route

    async def route(a, b, mode):
        if mode == "car":
            raise RoutingUnavailable("engine timed out")
        return await actual_route(a, b, mode)

    router = app.state.routing_provider
    monkeypatch.setattr(router, "route", AsyncMock(side_effect=route))
    response = await client.post("/v1/directions", json=PAYLOAD)
    assert response.status_code == 200, response.text
    assert [option["mode"] for option in response.json()] == ["walk", "scooter"]
    assert sum(call.args[2] == "car" for call in router.route.await_args_list) == 1


@pytest.mark.parametrize("error,status", [(NoRoute, 200), (RoutingUnavailable, 503)])
async def test_directions_empty_vs_unavailable(error, status, directions_api, monkeypatch):
    app, client, _ = directions_api
    monkeypatch.setattr(app.state.routing_provider, "route", AsyncMock(side_effect=error))
    response = await client.post("/v1/directions", json=PAYLOAD)
    assert response.status_code == status, response.text
    if status == 200:
        assert response.json() == []
    else:
        assert response.json()["error"]["code"] == "routing_unavailable"


async def test_directions_omits_long_walk(directions_api):
    _, client, _ = directions_api
    response = await client.post(
        "/v1/directions",
        json={**PAYLOAD, "to": {"lat": 43.35, "lon": 77.19}},
    )
    assert response.status_code == 200, response.text
    assert {option["mode"] for option in response.json()} == {"scooter", "car", "taxi"}


async def test_directions_free_walk_degrades_when_tariffs_unavailable(directions_api):
    _, client, tariffs = directions_api
    tariffs.side_effect = OperationalError("database down")
    response = await client.post("/v1/directions", json=PAYLOAD)
    assert response.status_code == 200, response.text
    assert [option["mode"] for option in response.json()] == ["walk"]


async def test_directions_transfer_pricing_and_geometry(directions_api, monkeypatch):
    _, client, tariffs = directions_api
    tariffs.return_value = {
        "metro": Tariff("metro", Decimal(120), Decimal(0), Decimal(0)),
        "bus": Tariff("bus", Decimal(100), Decimal(0), Decimal(0)),
    }
    middle = (43.25, 77.0)
    end = (43.25, 77.05)
    legs = [
        TransitLeg(
            "ride",
            200,
            2000,
            a,
            b,
            geometry=encode_polyline6([a, b]),
            route_ref=ref,
            kind=kind,
        )
        for a, b, ref, kind in (
            (ORIGIN, middle, "M", "metro"),
            (middle, end, "25", "trolleybus"),
        )
    ]
    monkeypatch.setattr(
        service,
        "find_transit_options",
        AsyncMock(return_value=[TransitOption("metro", "metro", 430, 1, legs)]),
    )
    payload = {**PAYLOAD, "to": {"lat": end[0], "lon": end[1]}}
    response = await client.post("/v1/directions", json=payload)
    assert response.status_code == 200, response.text
    [option] = response.json()
    assert option["mode"] == "metro"
    assert option["cost_kzt_min"] == option["cost_kzt_max"] == 220
    assert decode_polyline6(option["geometry"]) == [ORIGIN, middle, end]
    assert [step["route_ref"] for step in option["steps"]] == ["M", "25"]
    assert all(step["geometry"] for step in option["steps"])
    assert option["recommended"] is True
    tariffs.return_value.pop("metro")
    response = await client.post("/v1/directions", json=payload)
    assert response.status_code == 200, response.text
    assert response.json() == []


async def test_directions_place_and_tariff_version_in_postgis(conn):
    app = create_app()
    app.state.db = TransactionalDatabase(conn)
    app.state.routing_provider = FakeRouter()
    place_id = await add_place(conn, "Near", TARGET[1], TARGET[0])
    hidden_id = await add_place(conn, "Hidden", TARGET[1], TARGET[0], status="hidden")
    await execute(
        conn,
        """
        INSERT INTO transport_tariffs
            (mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, source)
        VALUES
            ('taxi', '2026-11-20', 100, 0, 0, 'test'),
            ('taxi', '2026-11-21', 200, 0, 0, 'test'),
            ('taxi', '2026-11-22', 300, 0, 0, 'test')
        """,
    )
    payload = {**PAYLOAD, "to": None, "to_place_id": str(place_id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/directions", json=payload)
        assert response.status_code == 200, response.text
        taxi = next(option for option in response.json() if option["mode"] == "taxi")
        assert taxi["cost_kzt_min"] == 200
        assert decode_polyline6(taxi["geometry"])[-1] == TARGET
        response = await client.post(
            "/v1/directions", json={**payload, "to_place_id": str(hidden_id)}
        )
        assert response.status_code == 404, response.text


async def test_directions_uses_valhalla_step_shapes(directions_api):
    app, client, _ = directions_api
    points = [ORIGIN, (43.251, 76.951), TARGET]
    data = {
        "trip": {
            "summary": {"time": 300, "length": 0.5},
            "legs": [
                {
                    "shape": encode_polyline6(points),
                    "maneuvers": [
                        {"instruction": "Continue", "begin_shape_index": 0, "end_shape_index": 1},
                        {"instruction": "Turn", "begin_shape_index": 1, "end_shape_index": 2},
                    ],
                },
            ],
        },
    }

    def handler(request):
        return Response(200, json=data)

    async with AsyncClient(transport=MockTransport(handler), base_url="http://routing") as engine:
        app.state.routing_provider = ValhallaRouter("http://routing", client=engine)
        response = await client.post("/v1/directions", json=PAYLOAD)
    assert response.status_code == 200, response.text
    walk = next(option for option in response.json() if option["mode"] == "walk")
    assert decode_polyline6(walk["geometry"]) == points
    assert [decode_polyline6(step["geometry"]) for step in walk["steps"]] == [
        points[:2],
        points[1:],
    ]


async def test_malformed_valhalla_response_is_unavailable(directions_api):
    app, client, _ = directions_api

    def handler(request):
        return Response(200, json={"unrelated": []})

    async with AsyncClient(transport=MockTransport(handler), base_url="http://routing") as engine:
        app.state.routing_provider = ValhallaRouter("http://routing", client=engine)
        response = await client.post("/v1/directions", json=PAYLOAD)
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "routing_unavailable"


async def test_directions_lifespan_closes_provider(monkeypatch):
    db = AsyncMock()
    provider = AsyncMock()
    monkeypatch.setattr(main, "Database", lambda *args: db)
    monkeypatch.setattr(main, "make_router", lambda url: provider)
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.routing_provider is provider
        provider.aclose.assert_not_awaited()
    provider.aclose.assert_awaited_once()
    db.close.assert_awaited_once()
