"""When does a day "suffer" from the weather (Ш-40, SSOT §7.1)? Explicit thresholds.

A stop suffers when it is outdoor and, during the hours of its visit, the forecast shows:
- thunderstorm (WMO 95/96/99) in ANY hour of the visit (safety, no share needed), or
- rain: precipitation probability >= RAIN_PROBABILITY in at least BAD_HOURS_SHARE of the known
  hours, or
- strong wind: >= STRONG_WIND_KMH in at least that share, or
- heat: >= HEAT_C in at least that share.
Priority of the reported kind: thunderstorm, rain, wind, heat. Hours the forecast does not know
are ignored; a stop with no known hour does not suffer (no information, nothing is moved).
RAIN_PROBABILITY is a little above the planner's 0.5 on purpose: a plan built under 0.5 is not
disturbed by a small wobble of the forecast. Mountains are stricter (MOUNTAIN_WIND_KMH, cold).
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from app.providers.weather.base import THUNDERSTORM_CODES, HourWeather

RAIN_PROBABILITY = 0.6
STRONG_WIND_KMH = 40.0  # Beaufort 6 (strong breeze) and up
HEAT_C = 35.0
BAD_HOURS_SHARE = 0.5
MOUNTAIN_WIND_KMH = 30.0  # exposed ridges: weaker wind already matters
MOUNTAIN_COLD_C = 0.0  # at the place's elevation


@dataclass(frozen=True)
class Problem:
    kind: str  # thunderstorm | rain | wind | heat | cold
    hours: Tuple[int, int]  # first and last bad local hour
    peak: Optional[float]  # rain probability 0..1 / wind km/h / temperature C; None for thunder


def visit_hours(start_min: int, end_min: int) -> range:
    """Local hours a visit [start, end) touches."""
    return range(start_min // 60, (end_min - 1) // 60 + 1)


def stop_problem(
    hours: Sequence[Optional[HourWeather]],
    start_min: int,
    end_min: int,
    wind_kmh: float = STRONG_WIND_KMH,
    cold_c: Optional[float] = None,
) -> Optional[Problem]:
    known = [(h, hours[h]) for h in visit_hours(start_min, end_min) if 0 <= h < len(hours)]
    known = [(h, w) for h, w in known if w is not None]
    if not known:
        return None
    thunder = [h for h, w in known if w.weather_code in THUNDERSTORM_CODES]
    if thunder:
        return Problem("thunderstorm", (thunder[0], thunder[-1]), None)

    def share_ok(bad: list) -> bool:
        return bool(bad) and len(bad) / len(known) >= BAD_HOURS_SHARE

    rain = [
        (h, w.rain_probability) for h, w in known if (w.rain_probability or 0) >= RAIN_PROBABILITY
    ]
    if share_ok(rain):
        return Problem("rain", (rain[0][0], rain[-1][0]), max(p for _, p in rain))
    wind = [(h, w.wind_kmh) for h, w in known if (w.wind_kmh or 0) >= wind_kmh]
    if share_ok(wind):
        return Problem("wind", (wind[0][0], wind[-1][0]), max(v for _, v in wind))
    heat = [(h, w.temperature_c) for h, w in known if (w.temperature_c or -99) >= HEAT_C]
    if share_ok(heat):
        return Problem("heat", (heat[0][0], heat[-1][0]), max(v for _, v in heat))
    if cold_c is not None:
        cold = [(h, w.temperature_c) for h, w in known if (w.temperature_c or 99) <= cold_c]
        if share_ok(cold):
            return Problem("cold", (cold[0][0], cold[-1][0]), min(v for _, v in cold))
    return None
