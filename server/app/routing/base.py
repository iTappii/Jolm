"""Routing provider interface, result types and errors (no HTTP details here)."""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

try:  # Python 3.9 has no typing.Protocol issues; kept explicit for clarity
    from typing import Protocol
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol  # type: ignore

# (lat, lon) in WGS84 degrees
Point = Tuple[float, float]

# Internal transport modes used by planner/directions. Public transport, taxi and
# own-car cost are derived elsewhere (Ш-21/22); 'car' geometry serves taxi and own car.
MODES = ("walk", "scooter", "car")


class RoutingError(Exception):
    """Base class for routing failures."""


class RoutingUnavailable(RoutingError):
    """Engine unreachable / timed out / returned a server error."""


class NoRoute(RoutingError):
    """Engine is up but there is no route between the points for this mode."""


@dataclass(frozen=True)
class Maneuver:
    instruction: str
    type: int
    length_m: float
    duration_s: float
    street_names: List[str] = field(default_factory=list)
    geometry: Optional[str] = None


@dataclass(frozen=True)
class RouteResult:
    mode: str
    duration_s: float
    distance_m: float
    geometry: str  # encoded polyline, precision 6 (as returned by Valhalla)
    maneuvers: List[Maneuver] = field(default_factory=list)


@dataclass(frozen=True)
class MatrixResult:
    """durations_s[i][j] / distances_m[i][j]: sources[i] -> targets[j]; None = unreachable."""

    mode: str
    durations_s: List[List[Optional[float]]]
    distances_m: List[List[Optional[float]]]


class RoutingProvider(Protocol):
    async def route(self, from_point: Point, to_point: Point, mode: str) -> RouteResult:
        """Raises NoRoute / RoutingUnavailable."""

    async def matrix(
        self, sources: Sequence[Point], targets: Sequence[Point], mode: str
    ) -> MatrixResult:
        """Unreachable pairs are None. Raises RoutingUnavailable."""

    async def aclose(self) -> None: ...


def check_mode(mode: str) -> str:
    if mode not in MODES:
        raise ValueError("unknown mode %r, expected one of %s" % (mode, MODES))
    return mode
