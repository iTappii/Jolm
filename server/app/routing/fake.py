"""Deterministic offline router for tests/dev: haversine x detour factor / mode speed."""

import math
from typing import Dict, Optional, Sequence

from app.routing.base import (
    MatrixResult,
    NoRoute,
    Point,
    RouteResult,
    check_mode,
)

EARTH_R_M = 6371008.8

# km/h, door-to-door city averages
SPEEDS_KMH: Dict[str, float] = {"walk": 4.8, "scooter": 15.0, "car": 28.0}
DETOUR: Dict[str, float] = {"walk": 1.25, "scooter": 1.3, "car": 1.35}
# beyond this the mode is "unreachable" (None / NoRoute), like a real engine's limits
MAX_DISTANCE_M: Dict[str, float] = {"walk": 100_000.0, "scooter": 100_000.0, "car": 1_000_000.0}


def haversine_m(a: Point, b: Point) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * EARTH_R_M * math.asin(math.sqrt(h))


def encode_polyline6(points: Sequence[Point]) -> str:
    out = []
    plat = plon = 0
    for lat, lon in points:
        ilat, ilon = int(round(lat * 1e6)), int(round(lon * 1e6))
        for d in (ilat - plat, ilon - plon):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        plat, plon = ilat, ilon
    return "".join(out)


class FakeRouter:
    def __init__(self, unreachable_over_m: Optional[Dict[str, float]] = None) -> None:
        self.max_m = dict(MAX_DISTANCE_M)
        if unreachable_over_m:
            self.max_m.update(unreachable_over_m)

    def _estimate(self, a: Point, b: Point, mode: str):
        dist = haversine_m(a, b) * DETOUR[mode]
        if dist > self.max_m[mode]:
            return None
        return dist / (SPEEDS_KMH[mode] / 3.6), dist

    async def route(self, from_point: Point, to_point: Point, mode: str) -> RouteResult:
        check_mode(mode)
        est = self._estimate(from_point, to_point, mode)
        if est is None:
            raise NoRoute("no %s route (fake: too far)" % mode)
        dur, dist = est
        return RouteResult(
            mode=mode,
            duration_s=round(dur, 1),
            distance_m=round(dist, 1),
            geometry=encode_polyline6([from_point, to_point]),
        )

    async def matrix(
        self, sources: Sequence[Point], targets: Sequence[Point], mode: str
    ) -> MatrixResult:
        check_mode(mode)
        durs, dists = [], []
        for s in sources:
            drow, lrow = [], []
            for t in targets:
                est = self._estimate(s, t, mode)
                drow.append(None if est is None else round(est[0], 1))
                lrow.append(None if est is None else round(est[1], 1))
            durs.append(drow)
            dists.append(lrow)
        return MatrixResult(mode=mode, durations_s=durs, distances_m=dists)

    async def aclose(self) -> None:
        return None
