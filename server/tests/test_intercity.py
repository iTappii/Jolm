"""Ш-60: intercity hubs/links seed, `GET /v1/intercity/options`, intercity taxi and car tariffs."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.routing import FakeRouter
from app.routing.base import RouteResult
from app.routing.costs import (
    IntercityParams,
    Tariff,
    calculate_cost,
    load_intercity_params,
    load_tariffs,
)
from app.routing.service import _road_option
from app.routing.valhalla import ValhallaRouter
from tests.conftest import ROOT, TransactionalDatabase
from tests.test_routing import VALHALLA, needs_valhalla

SEEDS = [ROOT / "data" / "seed" / "transport_tariffs.sql", ROOT / "data" / "seed" / "intercity.sql"]
ALMATY = (43.2389, 76.9455)
TURKESTAN = (43.2973, 68.2518)
SATY = (43.0706, 78.4088)
ASTANA = (51.1282, 71.4304)
SHYMKENT = (42.3417, 69.5901)
NOWHERE = (10.0, 10.0)  # outside every region


@pytest.fixture
async def seeded(conn):
    for seed in SEEDS:
        await conn.execute(seed.read_text(encoding="utf-8"))
    return conn


@pytest.fixture
async def api(seeded):
    app = create_app()
    app.state.db = TransactionalDatabase(seeded)
    app.state.routing_provider = FakeRouter()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield app, client


def query(a, b, **extra):
    return {"from_lat": a[0], "from_lon": a[1], "to_lat": b[0], "to_lon": b[1], **extra}


async def modes(client, a, b, **extra):
    response = await client.get("/v1/intercity/options", params=query(a, b, **extra))
    assert response.status_code == 200, response.text
    return response.json(), {o["mode"]: o for o in response.json()["options"]}


async def test_seed_has_every_pair_in_both_directions(seeded):
    cur = await seeded.execute("SELECT from_hub, to_hub, mode FROM intercity_links")
    links = {(r["from_hub"], r["to_hub"], r["mode"]) for r in await cur.fetchall()}
    assert len(links) >= 10
    city = {
        r["id"]: r["city_en"]
        for r in await (await seeded.execute("SELECT id, city_en FROM intercity_hubs")).fetchall()
    }
    pairs = {(city[a], city[b], m) for a, b, m in links}
    for a, b, m in pairs:
        assert (b, a, m) in pairs, (a, b, m)
    assert {"Turkistan", "Shymkent", "Astana", "Saty"} <= {c for _, c, _ in pairs}
    # honesty: every row is approximate and says where it came from
    rows = await (await seeded.execute("SELECT * FROM intercity_links")).fetchall()
    assert all(r["approximate"] and r["source"].strip() and r["as_of"] for r in rows)
    # no plane to Saty and no plane without both hubs being airports
    kinds = {
        r["id"]: r["kind"]
        for r in await (await seeded.execute("SELECT id, kind FROM intercity_hubs")).fetchall()
    }
    for a, b, m in links:
        if m == "plane":
            assert kinds[a] == kinds[b] == "airport"
        assert "saty" not in (a, b) or m == "tour"


async def test_seed_is_repeatable(seeded):
    before = (await (await seeded.execute("SELECT count(*) AS n FROM intercity_links")).fetchone())[
        "n"
    ]
    for seed in SEEDS:
        await seeded.execute(seed.read_text(encoding="utf-8"))
    after = (await (await seeded.execute("SELECT count(*) AS n FROM intercity_links")).fetchone())[
        "n"
    ]
    assert before == after


async def test_params_and_tariff_come_from_the_database(seeded):
    params = await load_intercity_params(seeded)
    assert params is not None and params.min_distance_km == 50
    assert params.fuel_per_km_kzt == Decimal("19.8")
    tariffs = await load_tariffs(seeded, date(2026, 11, 23))
    assert tariffs["taxi_intercity"].per_km_kzt > 0
    await seeded.execute("DELETE FROM intercity_settings")
    assert await load_intercity_params(seeded) is None


async def test_almaty_to_turkestan_has_plane_train_bus_car(api):
    _, client = api
    body, got = await modes(client, ALMATY, TURKESTAN, date="2026-12-01")
    assert {"plane", "train", "bus", "car", "taxi"} <= set(got)
    assert "tour" not in got
    assert body["from"]["region"] == "almaty" and body["to"]["region"] == "kazakhstan"
    plane = got["plane"]
    assert plane["approximate"] and plane["source"] and plane["as_of"] == "2026-11-23"
    assert plane["price_basis"] == "person" and got["car"]["price_basis"] == "vehicle"
    assert [leg["type"] for leg in plane["legs"]] == ["access", "wait", "main", "egress"]
    assert plane["duration_s_min"] <= plane["duration_s"] <= plane["duration_s_max"]
    assert plane["cost_kzt_min"] >= 15000  # ticket + two taxi legs
    assert sum(o["recommended"] for o in body["options"]) == 1
    durations = [o["duration_s"] for o in body["options"]]
    assert durations == sorted(durations)
    assert got["car"]["geometry"] and plane["geometry"] is None


async def test_turkestan_to_almaty_is_symmetric(api):
    _, client = api
    _, got = await modes(client, TURKESTAN, ALMATY)
    assert {"plane", "train", "bus", "car", "taxi"} <= set(got)


async def test_almaty_to_saty_has_car_taxi_tour_and_no_plane(api):
    _, client = api
    _, got = await modes(client, ALMATY, SATY)
    assert {"car", "taxi", "tour"} <= set(got)
    assert not {"plane", "train", "bus"} & set(got)
    assert got["tour"]["cost_kzt_min"] >= 13000


async def test_other_pairs_and_schedule_flag(api):
    _, client = api
    _, got = await modes(client, ALMATY, SHYMKENT, date="2026-12-02")  # a Wednesday
    assert {"plane", "train"} <= set(got)
    assert got["plane"]["schedule"]["days"] == [1, 2, 3, 4, 5, 6, 7]
    assert got["plane"]["schedule"]["runs_on_date"] is True
    assert got["train"]["schedule"]["runs_on_date"] is None  # unknown: never guessed
    _, got = await modes(client, ALMATY, ASTANA)
    assert {"plane", "train"} <= set(got)
    assert got["train"]["cost_kzt_min"] is None  # no fare found: null, not invented


async def test_short_trip_is_not_intercity(api):
    _, client = api
    body, got = await modes(client, ALMATY, (43.26, 76.95))
    assert body["options"] == []


async def test_points_outside_every_region_are_422(api):
    _, client = api
    for a, b in ((ALMATY, NOWHERE), (NOWHERE, ALMATY)):
        response = await client.get("/v1/intercity/options", params=query(a, b))
        assert response.status_code == 422
    response = await client.get("/v1/intercity/options", params={"from_lat": 1})
    assert response.status_code == 422


async def test_localised_names_and_rate_limit(api):
    app, client = api
    response = await client.get(
        "/v1/intercity/options",
        params=query(ALMATY, TURKESTAN),
        headers={"accept-language": "en"},
    )
    assert response.json()["options"][0]["legs"][0]["to_name"] is not None
    names = {leg["to_name"] for o in response.json()["options"] for leg in o["legs"]}
    assert "Almaty International Airport" in names or "Turkistan Airport" in names
    app.state.intercity_limiter.limit = 1
    again = await client.get("/v1/intercity/options", params=query(ALMATY, TURKESTAN))
    assert again.status_code == 429 and int(again.headers["Retry-After"]) >= 1


def test_intercity_taxi_is_cheaper_than_the_city_tariff_on_200_km():
    city = Tariff("taxi", Decimal(400), Decimal(30), Decimal(100))
    intercity = Tariff("taxi_intercity", Decimal(500), Decimal(0), Decimal(90))
    params = IntercityParams(50, 1500, Decimal("19.8"))
    route = RouteResult("car", 206_000 / 22.0, 206_000, "")  # ~2.6 h at 80 km/h
    plain = _road_option(route, "taxi", city, False, 1.6)
    over = _road_option(
        route, "taxi", city, False, 1.6, params, {"taxi": city, "taxi_intercity": intercity}
    )
    assert over.cost_kzt_max < plain.cost_kzt_max
    assert over.cost_kzt_min == over.cost_kzt_max == calculate_cost(intercity, 206_000, 0)[0]
    assert over.duration_s_max == pytest.approx(over.duration_s, abs=0.1)  # no traffic factor
    car = _road_option(route, "car", None, False, 1.6, params, {})
    assert car.cost_kzt_min == car.cost_kzt_max == round(206 * 19.8)
    short = RouteResult("car", 600, 5000, "")
    assert _road_option(
        short, "taxi", city, False, 1.6, params, {"taxi_intercity": intercity}
    ) == _road_option(short, "taxi", city, False, 1.6)


async def test_directions_uses_the_intercity_tariff_outside_the_city(seeded):
    app = create_app()
    app.state.db = TransactionalDatabase(seeded)
    app.state.routing_provider = FakeRouter()
    payload = {
        "from": {"lat": ALMATY[0], "lon": ALMATY[1]},
        "to": {"lat": 43.355, "lon": 79.077},  # Charyn, ~200 km
        "depart_at": "2026-11-25T10:00:00+06:00",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        far = {o["mode"]: o for o in (await client.post("/v1/directions", json=payload)).json()}
        await seeded.execute("DELETE FROM intercity_settings")  # without settings: city tariffs
        old = {o["mode"]: o for o in (await client.post("/v1/directions", json=payload)).json()}
    assert far["taxi"]["cost_kzt_max"] < old["taxi"]["cost_kzt_max"]
    assert far["taxi"]["duration_s_max"] == far["taxi"]["duration_s"]


@needs_valhalla
async def test_integration_valhalla_car_and_taxi_almaty_turkestan_and_saty(seeded):
    app = create_app()
    app.state.db = TransactionalDatabase(seeded)
    app.state.routing_provider = ValhallaRouter(VALHALLA)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            _, turk = await modes(c, ALMATY, TURKESTAN)
            _, saty = await modes(c, ALMATY, SATY)
    finally:
        await app.state.routing_provider.aclose()
    assert 700 <= turk["car"]["distance_m"] / 1000 <= 1000
    assert 7 * 3600 <= turk["car"]["duration_s"] <= 12 * 3600
    assert 250 <= saty["car"]["distance_m"] / 1000 <= 380
    assert 4 * 3600 <= saty["car"]["duration_s"] <= 7.5 * 3600
    # fuel by km (about 20 KZT/km) and the intercity taxi (90 KZT/km + 500)
    assert 12000 <= turk["car"]["cost_kzt_max"] <= 25000
    assert turk["taxi"]["cost_kzt_max"] < 100000
    assert saty["taxi"]["cost_kzt_max"] < 40000
    assert "plane" in turk and "plane" not in saty
