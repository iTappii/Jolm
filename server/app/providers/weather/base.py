"""Weather data and the provider interface (Ш-39, SSOT §7.1).

`WeatherProvider.forecast(lat, lon, days, elevation_m)` returns hourly weather for local
(Asia/Almaty) days. The planner reads it through `ForecastView`, which implements
`planner.weather.Forecast` (rain probability of a local hour); the weather re-check of Ш-40
reads the hours directly.
"""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Mapping, Optional, Protocol, Sequence

THUNDERSTORM_CODES = frozenset({95, 96, 99})  # WMO: counted as rain whatever the probability
RAIN_MM = 0.3  # precipitation in an hour at which a missing probability is read as "rain"


class WeatherUnavailable(Exception):
    """The provider could not supply the requested days (network, HTTP error, bad answer)."""


@dataclass(frozen=True)
class HourWeather:
    temperature_c: Optional[float]
    precipitation_probability: Optional[float]  # 0..1
    precipitation_mm: Optional[float]
    wind_kmh: Optional[float]
    weather_code: Optional[int]  # WMO code

    @property
    def rain_probability(self) -> Optional[float]:
        """0..1; Open-Meteo's probability, else derived from the amount; thunder is certain."""
        if self.weather_code in THUNDERSTORM_CODES:
            return 1.0
        if self.precipitation_probability is not None:
            return self.precipitation_probability
        if self.precipitation_mm is not None:
            return 1.0 if self.precipitation_mm >= RAIN_MM else 0.0
        return None


@dataclass(frozen=True)
class DayWeather:
    day: date
    hours: Sequence[Optional[HourWeather]]  # 24 entries, local hour 0..23; None = unknown


class WeatherProvider(Protocol):
    async def forecast(
        self, lat: float, lon: float, days: Sequence[date], elevation_m: Optional[float] = None
    ) -> Dict[date, DayWeather]:
        """Weather for the given local days. Days the source has no forecast for (past days,
        beyond its horizon) are absent. Raises `WeatherUnavailable` when nothing could be got."""


class ForecastView:
    """Planner adapter: `planner.weather.Forecast` over loaded days."""

    def __init__(self, days: Mapping[date, DayWeather]):
        self.days = dict(days)

    def rain_probability(self, day: date, hour: int) -> Optional[float]:
        weather = self.days.get(day)
        if weather is None or not 0 <= hour < len(weather.hours):
            return None
        point = weather.hours[hour]
        return point.rain_probability if point is not None else None

    def hours(self, day: date) -> List[Optional[HourWeather]]:
        weather = self.days.get(day)
        return list(weather.hours) if weather else []
