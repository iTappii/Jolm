"""Weather providers (Ш-39): `WeatherProvider` interface, Open-Meteo client, planner adapter."""

import logging
from datetime import date
from typing import Sequence

from app.planner.weather import Forecast, UnknownForecast
from app.providers.weather.base import (
    DayWeather,
    ForecastView,
    HourWeather,
    WeatherProvider,
    WeatherUnavailable,
)
from app.providers.weather.open_meteo import OpenMeteoProvider
from app.regions import default_region

log = logging.getLogger("app.weather")

__all__ = [
    "DayWeather",
    "ForecastView",
    "HourWeather",
    "OpenMeteoProvider",
    "WeatherProvider",
    "WeatherUnavailable",
    "city_forecast",
]


async def city_forecast(provider: WeatherProvider, days: Sequence[date]) -> Forecast:
    """The planner's `Forecast` for the region over `days`: real hours where the provider has them,
    `UnknownForecast` (no information, nothing is moved) when it is unavailable."""
    try:
        return ForecastView(await provider.forecast(*default_region().centre, days))
    except WeatherUnavailable:
        log.warning("no weather for the plan, planning without a forecast")
        return UnknownForecast()
