"""Async Valhalla client implementing RoutingProvider.

Internal modes ('walk', 'scooter', 'car') are mapped to Valhalla costing in ONE place
(COSTING below). 'scooter' approximates an e-scooter with the bicycle costing at ~15 km/h.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence

import httpx

from app.routing.base import (
    Maneuver,
    MatrixResult,
    NoRoute,
    Point,
    RouteResult,
    RoutingUnavailable,
    check_mode,
)

log = logging.getLogger("app.routing")

# mode -> (valhalla costing, costing_options for that costing)
COSTING: Dict[str, Dict[str, Any]] = {
    "walk": {"costing": "pedestrian", "options": {"walking_speed": 5.1}},
    "scooter": {
        "costing": "bicycle",
        "options": {
            "bicycle_type": "Hybrid",
            "cycling_speed": 15.0,
            "use_roads": 0.3,  # prefer bike lanes/paths over traffic
            "use_hills": 0.3,  # avoid steep climbs (scooter motors/riders dislike them)
            "avoid_bad_surfaces": 0.6,
        },
    },
    "car": {"costing": "auto", "options": {}},
}

# Valhalla "no route" codes: 154 too far for costing, 17x no path, 44x no edges near point
_NO_ROUTE_CODES = {154, 170, 171, 172, 442, 443, 444, 445}

MATRIX_MAX_LOCATIONS = 50  # valhalla default max_matrix_location_pairs is large; chunk anyway


def _loc(p: Point) -> Dict[str, float]:
    return {"lat": p[0], "lon": p[1]}


def _costing_body(mode: str) -> Dict[str, Any]:
    c = COSTING[check_mode(mode)]
    body: Dict[str, Any] = {"costing": c["costing"]}
    if c["options"]:
        body["costing_options"] = {c["costing"]: c["options"]}
    return body


def parse_route(mode: str, data: Dict[str, Any]) -> RouteResult:
    trip = data.get("trip") or {}
    legs = trip.get("legs") or []
    summary = trip.get("summary") or {}
    if not legs or "time" not in summary:
        raise NoRoute("empty route in response")
    if len(legs) == 1:
        geometry = legs[0]["shape"]
    else:  # multi-leg (not used for A->B); keep first leg shape, document limitation
        geometry = legs[0]["shape"]
    maneuvers: List[Maneuver] = []
    for leg in legs:
        for m in leg.get("maneuvers", []):
            maneuvers.append(
                Maneuver(
                    instruction=m.get("instruction", ""),
                    type=int(m.get("type", 0)),
                    length_m=round(float(m.get("length", 0.0)) * 1000, 1),
                    duration_s=float(m.get("time", 0.0)),
                    street_names=list(m.get("street_names", []) or []),
                )
            )
    return RouteResult(
        mode=mode,
        duration_s=float(summary["time"]),
        distance_m=round(float(summary["length"]) * 1000, 1),
        geometry=geometry,
        maneuvers=maneuvers,
    )


def parse_matrix(mode: str, data: Dict[str, Any], n_sources: int, n_targets: int) -> MatrixResult:
    rows = data.get("sources_to_targets")
    if rows is None:
        raise RoutingUnavailable("matrix response has no sources_to_targets")
    durs: List[List[Optional[float]]] = [[None] * n_targets for _ in range(n_sources)]
    dists: List[List[Optional[float]]] = [[None] * n_targets for _ in range(n_sources)]
    for row in rows:
        for cell in row:
            i, j = cell["from_index"], cell["to_index"]
            if cell.get("time") is None:
                continue
            durs[i][j] = float(cell["time"])
            if cell.get("distance") is not None:
                dists[i][j] = round(float(cell["distance"]) * 1000, 1)
    return MatrixResult(mode=mode, durations_s=durs, distances_m=dists)


class ValhallaRouter:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 10.0,
        retries: int = 2,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._retries = retries
        self._own_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_s, connect=3.0),
        )

    async def aclose(self) -> None:
        if self._own_client:
            await self._client.aclose()

    async def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        last: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                resp = await self._client.post(path, json=body)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:  # connection errors only
                last = e
                if attempt < self._retries:
                    await asyncio.sleep(0.2 * (2**attempt))
                    continue
                raise RoutingUnavailable("valhalla unreachable: %s" % e) from e
            except httpx.HTTPError as e:  # read timeout etc.: do not retry
                raise RoutingUnavailable("valhalla request failed: %s" % e) from e
            if resp.status_code == 200:
                return resp.json()
            code = None
            try:
                code = resp.json().get("error_code")
            except ValueError:
                pass
            if resp.status_code == 400 and code in _NO_ROUTE_CODES:
                raise NoRoute("no route (valhalla %s)" % code)
            if resp.status_code >= 500 or resp.status_code == 400:
                raise RoutingUnavailable(
                    "valhalla error %s: %s" % (resp.status_code, resp.text[:200])
                )
            raise RoutingUnavailable("valhalla unexpected status %s" % resp.status_code)
        raise RoutingUnavailable("valhalla unreachable: %s" % last)  # pragma: no cover

    async def route(self, from_point: Point, to_point: Point, mode: str) -> RouteResult:
        body = _costing_body(mode)
        body["locations"] = [_loc(from_point), _loc(to_point)]
        body["directions_options"] = {"units": "kilometers", "language": "en-US"}
        return parse_route(mode, await self._post("/route", body))

    async def _matrix_chunk(
        self, ss: Sequence[Point], tt: Sequence[Point], mode: str
    ) -> MatrixResult:
        body = _costing_body(mode)
        body["sources"] = [_loc(p) for p in ss]
        body["targets"] = [_loc(p) for p in tt]
        return parse_matrix(mode, await self._post("/sources_to_targets", body), len(ss), len(tt))

    async def _matrix_pairwise(
        self, ss: Sequence[Point], tt: Sequence[Point], mode: str
    ) -> MatrixResult:
        durs: List[List[Optional[float]]] = [[None] * len(tt) for _ in ss]
        dists: List[List[Optional[float]]] = [[None] * len(tt) for _ in ss]
        for i, a in enumerate(ss):
            for j, b in enumerate(tt):
                try:
                    one = await self._matrix_chunk([a], [b], mode)
                except NoRoute:
                    continue
                durs[i][j] = one.durations_s[0][0]
                dists[i][j] = one.distances_m[0][0]
        return MatrixResult(mode=mode, durations_s=durs, distances_m=dists)

    async def matrix(
        self, sources: Sequence[Point], targets: Sequence[Point], mode: str
    ) -> MatrixResult:
        n_s, n_t = len(sources), len(targets)
        durs: List[List[Optional[float]]] = [[None] * n_t for _ in range(n_s)]
        dists: List[List[Optional[float]]] = [[None] * n_t for _ in range(n_s)]
        if not n_s or not n_t:
            return MatrixResult(mode=mode, durations_s=durs, distances_m=dists)
        # chunk so each request stays under the engine's per-request location limits
        for s0 in range(0, n_s, MATRIX_MAX_LOCATIONS):
            for t0 in range(0, n_t, MATRIX_MAX_LOCATIONS):
                ss = sources[s0 : s0 + MATRIX_MAX_LOCATIONS]
                tt = targets[t0 : t0 + MATRIX_MAX_LOCATIONS]
                try:
                    part = await self._matrix_chunk(ss, tt, mode)
                except NoRoute:
                    # e.g. one pair exceeds the engine's distance limit: isolate it pair by pair
                    part = await self._matrix_pairwise(ss, tt, mode)
                for i in range(len(ss)):
                    for j in range(len(tt)):
                        durs[s0 + i][t0 + j] = part.durations_s[i][j]
                        dists[s0 + i][t0 + j] = part.distances_m[i][j]
        return MatrixResult(mode=mode, durations_s=durs, distances_m=dists)
