"""Forecast interface for the day layout (Ф11 provides the real one; Open-Meteo, SSOT §7.1).

Until Ф11 the forecast is unknown: `UnknownForecast` answers None for every hour, which the
layout reads as "no information": mountains go in the morning of the first day they are open,
and no place is moved because of rain.
"""

from datetime import date
from typing import Optional, Protocol

RAIN_PROBABILITY = 0.5  # an hour counts as rainy from this precipitation probability


class Forecast(Protocol):
    def rain_probability(self, day: date, hour: int) -> Optional[float]:
        """0..1 for the local hour (Asia/Almaty), or None when unknown."""


class UnknownForecast:
    def rain_probability(self, day: date, hour: int) -> Optional[float]:
        return None


def is_rainy(forecast: Forecast, day: date, hour: int) -> bool:
    p = forecast.rain_probability(day, hour)
    return p is not None and p >= RAIN_PROBABILITY
