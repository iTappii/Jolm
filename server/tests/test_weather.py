"""Ш-39: Open-Meteo client, database cache and the planner adapter.

No network: the HTTP layer is httpx.MockTransport answering with a response recorded from the
real API (tests/fixtures/open_meteo).
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.db import fetch_all, fetch_one
from app.planner.weather import UnknownForecast, is_rainy
from app.providers.weather import (
    DayWeather,
    ForecastView,
    HourWeather,
    OpenMeteoProvider,
    WeatherUnavailable,
    city_forecast,
)
from app.providers.weather.open_meteo import (
    FREE_URL,
    PAID_URL,
    cache_key,
    parse_response,
)
from tests.conftest import TransactionalDatabase

FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"
CENTER = json.loads((FIXTURES / "almaty_center.json").read_text())  # 2026-11-22 .. 2026-11-24
MEDEU = json.loads((FIXTURES / "medeu_elevation.json").read_text())  # 2026-11-22, elevation 1700
NOW = datetime(2026, 11, 21, 7, 0, tzinfo=timezone.utc)  # 12:00 in Almaty
D22, D23, D24, D25 = (date(2026, 11, d) for d in (22, 23, 24, 25))


def body_for(template, start, end):
    """The recorded response, relabelled/sliced to the dates asked for (the fixture has 3 days;
    a day past it repeats its last day)."""
    hourly = template["hourly"]
    times = hourly["time"]
    first = date.fromisoformat(times[0][:10])
    out = {k: [] for k in hourly}
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        src = min(max((day - first).days, 0), len(times) // 24 - 1)
        for hour in range(24):
            for key, values in hourly.items():
                out[key].append(
                    "%sT%02d:00" % (day.isoformat(), hour) if key == "time"
                    else values[src * 24 + hour]
                )  # fmt: skip
    return dict(template, hourly=out)


class FakeOpenMeteo:
    """MockTransport handler: records the requests, answers from a fixture or fails."""

    def __init__(self, template=CENTER):
        self.template, self.requests, self.fail = template, [], None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail is not None:
            return httpx.Response(self.fail)
        q = request.url.params
        start, end = date.fromisoformat(q["start_date"]), date.fromisoformat(q["end_date"])
        return httpx.Response(200, json=body_for(self.template, start, end))


class Clock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now


def make(conn, fake, clock=None, **kwargs):
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    return OpenMeteoProvider(
        TransactionalDatabase(conn), FREE_URL, client=client, clock=clock or Clock(), **kwargs
    )


# --- parsing the recorded response ----------------------------------------------------------
def test_parse_the_recorded_response():
    days = parse_response(CENTER)
    assert sorted(days) == [D22, D23, D24]
    first = days[D22]
    assert len(first.hours) == 24 and all(h is not None for h in first.hours)
    hour = first.hours[4]  # 2026-11-22 04:00: fog (WMO 45), 2 % precipitation probability
    assert hour.weather_code == 45 and hour.precipitation_probability == pytest.approx(0.02)
    assert hour.temperature_c == CENTER["hourly"]["temperature_2m"][4]
    assert hour.wind_kmh == CENTER["hourly"]["wind_speed_10m"][4]
    assert hour.precipitation_mm == CENTER["hourly"]["precipitation"][4]
    assert all(0.0 <= h.precipitation_probability <= 1.0 for d in days.values() for h in d.hours)


def test_parse_rejects_a_broken_answer():
    broken = json.loads(json.dumps(CENTER))
    broken["hourly"]["precipitation"] = broken["hourly"]["precipitation"][:-1]
    with pytest.raises(ValueError):
        parse_response(broken)
    with pytest.raises(KeyError):
        parse_response({"error": True})


def test_cache_key_rounds_the_point_and_the_elevation():
    assert cache_key(43.2389, 76.9455, None) == (4324, 7695, -1)
    assert cache_key(43.2412, 76.9488, None) == (4324, 7695, -1)  # the same ~1 km cell
    assert cache_key(43.157, 77.059, 1691) == (4316, 7706, 1700)
    assert cache_key(43.157, 77.059, 1749) == (4316, 7706, 1700)
    assert cache_key(43.157, 77.059, 1751) == (4316, 7706, 1800)


# --- the client and its cache ---------------------------------------------------------------
async def test_fetches_the_forecast_for_the_rounded_point_and_caches_each_day(conn):
    fake = FakeOpenMeteo()
    provider = make(conn, fake)
    result = await provider.forecast(43.2389, 76.9455, [D22, D23, D24])
    assert sorted(result) == [D22, D23, D24]
    [request] = fake.requests
    assert request.url.host == "api.open-meteo.com" and request.url.path == "/v1/forecast"
    q = request.url.params
    assert q["latitude"] == "43.24" and q["longitude"] == "76.95"  # the rounded point
    assert q["timezone"] == "Asia/Almaty"
    assert q["start_date"] == "2026-11-22" and q["end_date"] == "2026-11-24"
    assert set(q["hourly"].split(",")) == {
        "temperature_2m", "precipitation_probability", "precipitation", "wind_speed_10m",
        "weather_code",
    }  # fmt: skip
    assert "elevation" not in q and "apikey" not in q
    rows = await fetch_all(conn, "SELECT * FROM weather_cache ORDER BY day")
    assert [r["day"] for r in rows] == [D22, D23, D24]
    assert {(r["lat_e2"], r["lon_e2"], r["elevation_key"]) for r in rows} == {(4324, 7695, -1)}
    assert all(len(r["hourly"]) == 24 for r in rows) and rows[0]["fetched_at"] == NOW


async def test_a_second_call_and_a_nearby_point_are_served_from_the_cache(conn):
    fake = FakeOpenMeteo()
    provider = make(conn, fake)
    first = await provider.forecast(43.2389, 76.9455, [D22, D23])
    again = await provider.forecast(43.2389, 76.9455, [D22, D23])
    nearby = await provider.forecast(43.2412, 76.9488, [D22])  # same 0.01 degree cell
    assert len(fake.requests) == 1
    assert again == first and nearby[D22] == first[D22]
    # a fresh provider (another process) uses the same table
    other = make(conn, fake)
    assert await other.forecast(43.2389, 76.9455, [D23]) == {D23: first[D23]}
    assert len(fake.requests) == 1


async def test_only_the_missing_days_are_fetched(conn):
    fake = FakeOpenMeteo()
    provider = make(conn, fake)
    await provider.forecast(43.24, 76.95, [D22, D23])
    result = await provider.forecast(43.24, 76.95, [D22, D23, D24, D25])
    assert sorted(result) == [D22, D23, D24, D25]
    assert len(fake.requests) == 2
    q = fake.requests[1].url.params
    assert q["start_date"] == "2026-11-24" and q["end_date"] == "2026-11-25"


async def test_ttl_is_three_hours_then_the_forecast_is_fetched_again(conn):
    fake, clock = FakeOpenMeteo(), Clock()
    provider = make(conn, fake, clock)
    await provider.forecast(43.24, 76.95, [D22])
    clock.now = NOW + timedelta(hours=2, minutes=59)
    await provider.forecast(43.24, 76.95, [D22])
    assert len(fake.requests) == 1
    clock.now = NOW + timedelta(hours=3, minutes=1)
    await provider.forecast(43.24, 76.95, [D22])
    assert len(fake.requests) == 2
    row = await fetch_one(conn, "SELECT fetched_at FROM weather_cache")
    assert row["fetched_at"] == clock.now  # the row was refreshed, not duplicated
    assert len(await fetch_all(conn, "SELECT 1 FROM weather_cache")) == 1


async def test_mountains_send_the_elevation_and_have_their_own_cache_rows(conn):
    fake = FakeOpenMeteo(MEDEU)
    provider = make(conn, fake)
    peak = await provider.forecast(43.157, 77.059, [D22], elevation_m=1691)
    q = fake.requests[0].url.params
    assert q["latitude"] == "43.16" and q["longitude"] == "77.06" and q["elevation"] == "1700"
    town = await provider.forecast(43.157, 77.059, [D22])  # same point, no elevation: another key
    assert len(fake.requests) == 2 and "elevation" not in fake.requests[1].url.params
    rows = await fetch_all(conn, "SELECT elevation_key FROM weather_cache ORDER BY elevation_key")
    assert [r["elevation_key"] for r in rows] == [-1, 1700]
    assert peak[D22].hours[0].temperature_c == MEDEU["hourly"]["temperature_2m"][0] == 6.2
    assert town[D22] is not None


async def test_days_outside_the_forecast_horizon_are_not_requested(conn):
    fake = FakeOpenMeteo()
    provider = make(conn, fake)
    past, far = date(2026, 11, 20), NOW.date() + timedelta(days=16)
    assert await provider.forecast(43.24, 76.95, [past, far]) == {}
    assert fake.requests == []
    result = await provider.forecast(43.24, 76.95, [past, D22, NOW.date() + timedelta(days=15)])
    assert sorted(result) == [D22, NOW.date() + timedelta(days=15)]
    assert fake.requests[0].url.params["start_date"] == "2026-11-22"


async def test_when_the_api_fails_a_stale_cache_is_used_for_a_day(conn):
    fake, clock = FakeOpenMeteo(), Clock()
    provider = make(conn, fake, clock)
    fresh = await provider.forecast(43.24, 76.95, [D22, D23])
    fake.fail = 500
    clock.now = NOW + timedelta(hours=10)  # past the TTL, inside the 24 h stale window
    assert await provider.forecast(43.24, 76.95, [D22, D23]) == fresh
    clock.now = NOW + timedelta(hours=25)  # too old to trust
    with pytest.raises(WeatherUnavailable):
        await provider.forecast(43.24, 76.95, [D22, D23])


async def test_a_failure_without_any_cache_raises_and_stores_nothing(conn):
    fake = FakeOpenMeteo()
    fake.fail = 503
    provider = make(conn, fake)
    with pytest.raises(WeatherUnavailable):
        await provider.forecast(43.24, 76.95, [D22])
    assert await fetch_all(conn, "SELECT 1 FROM weather_cache") == []


async def test_an_error_body_with_status_200_is_a_failure_too(conn):
    def error_body(request):
        return httpx.Response(200, json={"error": True, "reason": "Latitude must be in range"})

    provider = make(conn, error_body)
    with pytest.raises(WeatherUnavailable):
        await provider.forecast(43.24, 76.95, [D22])
    assert await fetch_all(conn, "SELECT 1 FROM weather_cache") == []


async def test_the_paid_plan_uses_the_customer_host_and_the_key(conn, monkeypatch):
    monkeypatch.setattr(get_settings(), "open_meteo_api_key", SecretStr("secret-key"))
    fake = FakeOpenMeteo()
    provider = OpenMeteoProvider.from_settings(
        TransactionalDatabase(conn), httpx.AsyncClient(transport=httpx.MockTransport(fake))
    )
    provider.clock = Clock()
    await provider.forecast(43.24, 76.95, [D22])
    request = fake.requests[0]
    assert request.url.host == "customer-api.open-meteo.com" and PAID_URL in str(request.url)
    assert request.url.params["apikey"] == "secret-key"


async def test_without_a_key_the_free_host_is_used(conn, monkeypatch):
    monkeypatch.setattr(get_settings(), "open_meteo_api_key", SecretStr(""))
    provider = OpenMeteoProvider.from_settings(TransactionalDatabase(conn))
    assert provider.base_url == FREE_URL and provider.api_key is None


# --- planner adapter ------------------------------------------------------------------------
async def test_the_planner_reads_rain_probability_per_local_hour(conn):
    provider = make(conn, FakeOpenMeteo())
    view = await city_forecast(provider, [D22, D23, D24])
    assert isinstance(view, ForecastView)
    probs = CENTER["hourly"]["precipitation_probability"]
    assert view.rain_probability(D22, 10) == pytest.approx(probs[10] / 100)
    assert view.rain_probability(D23, 3) == pytest.approx(probs[24 + 3] / 100)
    assert view.rain_probability(D25, 10) is None  # not loaded: unknown
    assert view.rain_probability(D22, 24) is None
    assert is_rainy(view, D22, 4) is False


def test_rain_rules_thunder_amount_and_unknown():
    thunder = HourWeather(10, 0.1, 0.0, 5, 95)
    assert thunder.rain_probability == 1.0
    no_prob_wet = HourWeather(10, None, 0.6, 5, 61)
    no_prob_dry = HourWeather(10, None, 0.0, 5, 3)
    nothing = HourWeather(10, None, None, 5, None)
    assert (no_prob_wet.rain_probability, no_prob_dry.rain_probability) == (1.0, 0.0)
    assert nothing.rain_probability is None
    view = ForecastView({D22: DayWeather(D22, [thunder] + [None] * 23)})
    assert is_rainy(view, D22, 0) and view.rain_probability(D22, 1) is None


async def test_a_rainy_forecast_moves_the_planner_not_the_unknown_one(conn):
    """A wet day through the adapter is read by the layout like any forecast."""
    view = ForecastView(
        {
            D22: DayWeather(D22, [HourWeather(5, 0.9, 2.0, 10, 63)] * 24),
            D23: DayWeather(D23, [HourWeather(5, 0.0, 0.0, 10, 1)] * 24),
        }
    )
    assert all(is_rainy(view, D22, h) for h in range(24))
    assert not any(is_rainy(view, D23, h) for h in range(24))


async def test_city_forecast_falls_back_to_unknown_when_the_provider_is_down(conn):
    fake = FakeOpenMeteo()
    fake.fail = 500
    forecast = await city_forecast(make(conn, fake), [D22])
    assert isinstance(forecast, UnknownForecast)
    assert forecast.rain_probability(D22, 12) is None
