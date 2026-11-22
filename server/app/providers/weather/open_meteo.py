"""Open-Meteo Forecast API client with a database cache (Ш-39).

Request: hourly temperature_2m, precipitation_probability, precipitation, wind_speed_10m,
weather_code in the region time zone for a date range; for mountain places the point AND its
elevation are sent (`elevation`), so the temperature is corrected to the place's height.

Cache (table `weather_cache`, migration 0013): key = coordinates rounded to 0.01 degree (about
1 km; the request itself uses the rounded point, so the cached data matches its key), elevation
rounded to 100 m, local day. A day is served from the cache while its row is younger than
`ttl_sec` (3 h); stale days are fetched again in ONE request for the missing range. If the fetch
fails, rows younger than `stale_sec` (24 h) are served instead; with nothing usable the call
raises `WeatherUnavailable`. The database is not held during the HTTP request.

Terms (verified 2026-11-21 at open-meteo.com/en/terms): the free API is for NON-commercial use
only (<10 000 calls/day, 5 000/hour, 600/minute, CC BY 4.0 attribution). Jol earns from partners,
so production needs the paid plan: set OPEN_METEO_API_KEY (calls then go to
customer-api.open-meteo.com with `apikey`). Attribution ("Weather data by Open-Meteo.com") has
to be shown in the app either way.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import httpx
from psycopg.types.json import Jsonb

from app.config import get_settings
from app.db import execute, fetch_all
from app.providers.weather.base import DayWeather, HourWeather, WeatherUnavailable
from app.regions import default_region

log = logging.getLogger("app.weather")

FREE_URL = "https://api.open-meteo.com"
PAID_URL = "https://customer-api.open-meteo.com"
HOURLY = "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code"
HORIZON_DAYS = 16  # Open-Meteo forecasts today + 15 days
TTL_SEC = 3 * 3600
STALE_SEC = 24 * 3600
TIMEOUT_SEC = 10.0
ELEVATION_STEP_M = 100


def cache_key(lat: float, lon: float, elevation_m: Optional[float]) -> Tuple[int, int, int]:
    elevation = (
        -1
        if elevation_m is None
        else max(0, int(round(elevation_m / ELEVATION_STEP_M))) * ELEVATION_STEP_M
    )
    return int(round(lat * 100)), int(round(lon * 100)), elevation


def _hour(raw: Dict[str, Any]) -> Optional[HourWeather]:
    if all(raw.get(k) is None for k in ("t", "p", "mm", "w", "c")):
        return None
    return HourWeather(raw.get("t"), raw.get("p"), raw.get("mm"), raw.get("w"), raw.get("c"))


def _hour_json(hour: Optional[HourWeather]) -> Dict[str, Any]:
    if hour is None:
        return {}
    return {
        "t": hour.temperature_c,
        "p": hour.precipitation_probability,
        "mm": hour.precipitation_mm,
        "w": hour.wind_kmh,
        "c": hour.weather_code,
    }


def parse_response(body: Dict[str, Any]) -> Dict[date, DayWeather]:
    """Open-Meteo hourly arrays -> days of 24 local hours. Raises ValueError on a bad shape."""
    hourly = body["hourly"]
    times: List[str] = hourly["time"]

    def column(name: str) -> List[Any]:
        values = hourly.get(name)
        if values is None:
            return [None] * len(times)
        if len(values) != len(times):
            raise ValueError(
                "column %s has %d values for %d hours" % (name, len(values), len(times))
            )
        return values

    temp, prob = column("temperature_2m"), column("precipitation_probability")
    rain, wind, code = column("precipitation"), column("wind_speed_10m"), column("weather_code")
    days: Dict[date, List[Optional[HourWeather]]] = {}
    for i, stamp in enumerate(times):
        day = date.fromisoformat(stamp[:10])
        hour = int(stamp[11:13])
        slots = days.setdefault(day, [None] * 24)
        slots[hour] = _hour(
            {
                "t": temp[i],
                "p": None if prob[i] is None else prob[i] / 100.0,
                "mm": rain[i],
                "w": wind[i],
                "c": None if code[i] is None else int(code[i]),
            }
        )
    return {d: DayWeather(d, tuple(slots)) for d, slots in days.items()}


class OpenMeteoProvider:
    def __init__(
        self,
        db: Any,
        base_url: str = FREE_URL,
        api_key: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        ttl_sec: float = TTL_SEC,
        stale_sec: float = STALE_SEC,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.db = db
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.client = client or httpx.AsyncClient(timeout=TIMEOUT_SEC)
        self.ttl = timedelta(seconds=ttl_sec)
        self.stale = timedelta(seconds=stale_sec)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_settings(
        cls, db: Any, client: Optional[httpx.AsyncClient] = None
    ) -> "OpenMeteoProvider":
        settings = get_settings()
        key = settings.open_meteo_api_key.get_secret_value()
        url = settings.open_meteo_url
        if key and url.rstrip("/") == FREE_URL:
            url = PAID_URL  # a key only works on the commercial host
        return cls(db, url, key, client)

    def _today(self) -> date:
        return self.clock().astimezone(default_region().tz).date()

    async def forecast(
        self, lat: float, lon: float, days: Sequence[date], elevation_m: Optional[float] = None
    ) -> Dict[date, DayWeather]:
        today = self._today()
        wanted = sorted({d for d in days if today <= d < today + timedelta(days=HORIZON_DAYS)})
        if not wanted:
            return {}
        lat_e2, lon_e2, elevation = cache_key(lat, lon, elevation_m)
        now = self.clock()
        async with self.db.transaction() as conn:
            rows = await fetch_all(
                conn,
                "SELECT day, hourly, fetched_at FROM weather_cache WHERE lat_e2 = %s "
                "AND lon_e2 = %s AND elevation_key = %s AND day = ANY(%s)",
                (lat_e2, lon_e2, elevation, wanted),
            )
        cached = {r["day"]: r for r in rows}
        result: Dict[date, DayWeather] = {}
        missing: List[date] = []
        for d in wanted:
            row = cached.get(d)
            if row is not None and now - row["fetched_at"] <= self.ttl:
                result[d] = self._from_row(d, row)
            else:
                missing.append(d)
        if missing:
            try:
                fresh = await self._fetch(lat_e2, lon_e2, elevation, missing[0], missing[-1])
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                log.warning(
                    "open-meteo fetch failed (%s), trying the stale cache", type(exc).__name__
                )
                fresh = {}
                for d in missing:
                    row = cached.get(d)
                    if row is not None and now - row["fetched_at"] <= self.stale:
                        result[d] = self._from_row(d, row)
                if not result:
                    raise WeatherUnavailable("open-meteo unavailable") from None
            else:
                await self._store(lat_e2, lon_e2, elevation, fresh, now)
                result.update({d: w for d, w in fresh.items() if d in missing})
        return result

    @staticmethod
    def _from_row(day: date, row: Dict[str, Any]) -> DayWeather:
        return DayWeather(day, tuple(_hour(h) for h in row["hourly"]))

    async def _fetch(
        self, lat_e2: int, lon_e2: int, elevation: int, start: date, end: date
    ) -> Dict[date, DayWeather]:
        params: Dict[str, Any] = {
            "latitude": lat_e2 / 100.0,
            "longitude": lon_e2 / 100.0,
            "hourly": HOURLY,
            "timezone": default_region().timezone,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        if elevation >= 0:
            params["elevation"] = elevation
        if self.api_key:
            params["apikey"] = self.api_key
        response = await self.client.get(self.base_url + "/v1/forecast", params=params)
        response.raise_for_status()
        return parse_response(response.json())

    async def _store(
        self, lat_e2: int, lon_e2: int, elevation: int, days: Dict[date, DayWeather], now: datetime
    ) -> None:
        async with self.db.transaction() as conn:
            for d, weather in days.items():
                await execute(
                    conn,
                    """
                    INSERT INTO weather_cache
                        (lat_e2, lon_e2, elevation_key, day, hourly, fetched_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (lat_e2, lon_e2, elevation_key, day)
                    DO UPDATE SET hourly = EXCLUDED.hourly, fetched_at = EXCLUDED.fetched_at
                    """,
                    (
                        lat_e2, lon_e2, elevation, d,
                        Jsonb([_hour_json(h) for h in weather.hours]), now,
                    ),
                )  # fmt: skip

    async def aclose(self) -> None:
        await self.client.aclose()
