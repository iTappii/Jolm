"""Travel time between stops for the day layout (Ш-34). Two separate jobs, two interfaces.

1. `TravelMatrixProvider`: one planning time (minutes) for every pair of points, used to order
   stops inside a day. Real: `RouterMatrix` over Valhalla `sources_to_targets`; if Valhalla is
   down or has no route for a pair it falls back to a haversine estimate and flags the result
   `estimated`. Tests and dev: `HaversineMatrix` (no network, deterministic).
2. `LegProvider`: all transport options for one transition, from the Ш-22 option builder
   (`routing.service.get_directions`). The default leg is its recommended option.

Planning time for a pair: the walking time if the walk takes at most 15 minutes, otherwise the
car time plus a 5-minute wait for the taxi. This matches the Ш-22 recommendation (short walks
first, then the fastest) without knowing which option the tourist will choose.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from app.routing.base import Point, RoutingProvider, RoutingUnavailable
from app.routing.costs import Tariff, recommend
from app.routing.fake import FakeRouter
from app.routing.schemas import DirectionOption
from app.routing.service import get_directions
from app.routing.transit import TransitNetwork

log = logging.getLogger(__name__)

WALK_PLAN_MAX_S = 15 * 60
TAXI_WAIT_S = 5 * 60


class TravelTimes:
    """Planning seconds between points `points[i] -> points[j]`."""

    def __init__(self, points: Sequence[Point], seconds: List[List[float]], estimated: bool):
        self.points = list(points)
        self.seconds = seconds
        self.estimated = estimated

    def minutes(self, i: int, j: int) -> int:
        if i == j:
            return 0
        return int(-(-self.seconds[i][j] // 60))  # ceil


class TravelMatrixProvider(Protocol):
    async def build(self, points: Sequence[Point]) -> TravelTimes: ...


def _plan_seconds(walk_s: Optional[float], car_s: Optional[float]) -> Optional[float]:
    if walk_s is not None and walk_s <= WALK_PLAN_MAX_S:
        return walk_s
    if car_s is not None:
        return car_s + TAXI_WAIT_S
    return walk_s


class RouterMatrix:
    """Walk and car matrices from a `RoutingProvider`, merged into planning times."""

    def __init__(self, router: RoutingProvider, estimated: bool = False):
        self.router = router
        self.estimated = estimated

    async def build(self, points: Sequence[Point]) -> TravelTimes:
        try:
            walk = await self.router.matrix(points, points, "walk")
            car = await self.router.matrix(points, points, "car")
        except RoutingUnavailable:
            log.warning("matrix unavailable, falling back to haversine estimates")
            return await HaversineMatrix().build(points, flagged=True)
        fallback = None
        estimated = self.estimated
        n = len(points)
        out: List[List[float]] = []
        for i in range(n):
            row = []
            for j in range(n):
                value = _plan_seconds(walk.durations_s[i][j], car.durations_s[i][j])
                if value is None:  # no route either way: estimate this pair
                    if fallback is None:
                        fallback = await HaversineMatrix().build(points, flagged=True)
                    value = fallback.seconds[i][j]
                    estimated = True
                row.append(value)
            out.append(row)
        return TravelTimes(points, out, estimated)


class HaversineMatrix(RouterMatrix):
    """Offline estimate from straight-line distance (routing.fake speeds). Always `estimated`."""

    def __init__(self) -> None:
        super().__init__(FakeRouter(), estimated=True)

    async def build(self, points: Sequence[Point], flagged: bool = True) -> TravelTimes:
        walk = await self.router.matrix(points, points, "walk")
        car = await self.router.matrix(points, points, "car")
        out = [
            [
                _plan_seconds(walk.durations_s[i][j], car.durations_s[i][j]) or 0.0
                for j in range(len(points))
            ]
            for i in range(len(points))
        ]
        return TravelTimes(points, out, True)


class LegProvider(Protocol):
    async def options(
        self, origin: Point, destination: Point, depart_at: datetime
    ) -> List[DirectionOption]:
        """All transport options for one transition; [] when none can be computed."""


class DirectionsLegs:
    """Ш-22 option builder behind the `LegProvider` interface, with a per-plan cache."""

    def __init__(
        self,
        router: RoutingProvider,
        network: Optional[TransitNetwork],
        tariffs: Dict[str, Tariff],
    ):
        self.router, self.network, self.tariffs = router, network, tariffs
        self._cache: Dict[Tuple[Point, Point, str], List[DirectionOption]] = {}

    async def options(
        self, origin: Point, destination: Point, depart_at: datetime
    ) -> List[DirectionOption]:
        # Traffic and timetables change by the hour; a 30-minute bucket is accurate enough.
        key = (origin, destination, depart_at.strftime("%Y-%m-%d %H") + str(depart_at.minute // 30))
        if key not in self._cache:
            try:
                self._cache[key] = await get_directions(
                    self.router, self.network, self.tariffs, origin, destination, depart_at
                )
            except RoutingUnavailable:
                self._cache[key] = []
        return self._cache[key]


class PreferredLegs:
    """`LegProvider` wrapper (Ш-38): where the person chose a transport mode for a transition,
    that option becomes the default (`recommended`) again, so re-timing a day after an edit
    keeps their choices. `prefs` maps (origin, destination) points to a mode."""

    def __init__(self, inner: LegProvider, prefs: Dict[Tuple[Point, Point], str]):
        self.inner, self.prefs = inner, prefs

    async def options(
        self, origin: Point, destination: Point, depart_at: datetime
    ) -> List[DirectionOption]:
        options = await self.inner.options(origin, destination, depart_at)
        mode = self.prefs.get((origin, destination))
        if mode is None or not any(o.mode == mode for o in options):
            return options
        return [o.model_copy(update={"recommended": o.mode == mode}) for o in options]


def pick_default(options: Sequence[DirectionOption]) -> Optional[DirectionOption]:
    """The default leg: the option Ш-22 marks `recommended` (walk up to 15 minutes, otherwise
    the lowest duration + 1 second per tenge of the upper cost). Recomputed if no flag is set."""
    for option in options:
        if option.recommended:
            return option
    index = recommend(
        [o.model_dump(include={"mode", "duration_s", "cost_kzt_max"}) for o in options]
    )
    return options[index] if index is not None else None


def leg_seconds(option: DirectionOption) -> float:
    """Time the schedule reserves: the upper bound for motor modes (traffic), else as is."""
    return option.duration_s_max or option.duration_s
