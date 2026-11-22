"""Public transport search (TECH_PLAN Ш-21): A -> B, at most one transfer. All times approximate.

There is no official GTFS/timetable for the region, so the model is deliberately simple:

    total = walk A->boarding stop            (RoutingProvider pedestrian matrix, real streets)
          + wait  = headway / 2              (average wait for a vehicle)
          + ride  = distance along the route between the stops / commercial speed
          [+ transfer walk (straight line x detour) + wait headway / 2 + ride]
          + walk alighting stop -> B         (pedestrian matrix)

Every option is flagged ``approximate=True``. Headways/speeds are per-route values from
``transit_routes`` (seeded from data/seed/transit_manual.csv; see there for the assumptions).

Direction: an OSM relation is one direction. A line (kind+ref) mapped with a single relation gets
its opposite direction inferred (reversed stop list, ``Route.inferred_reverse``).

Design choice, in-memory network: one region has ~1k stops and ~120 route directions (~5k route-stop
rows). The network is read with two SQL queries once per process (``get_network`` caches it for
``CACHE_TTL_S``; the OSM import is a rare offline job) and searched in Python: finding 1-transfer
itineraries is a graph join that would otherwise need several round trips or a large self-join per
request, while the in-memory version answers in a few ms. Walking legs to/from A and B use the
RoutingProvider, so Valhalla gives real street distances and tests use FakeRouter.

Output is tagged by the primary vehicle (the ride leg that takes longest): ``mode`` is ``'metro'``
or ``'bus'`` (bus/trolleybus/tram), ``kind`` keeps the exact vehicle. POST /directions (Ш-22)
adds fares and merges with the other modes.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.db import fetch_all
from app.regions import default_region
from app.routing.base import Point, RoutingError, RoutingProvider
from app.routing.fake import encode_polyline6, haversine_m

# --- tunable assumptions ----------------------------------------------------------------------

MAX_WALK_RADIUS_M = 1000.0  # candidate stops: straight-line radius around A / B
MAX_WALK_M = 1400.0  # reject candidates whose real walking distance is longer
MAX_CANDIDATE_STOPS = 24  # per end; nearest stop of every passing route first
TRANSFER_RADIUS_M = 300.0  # stops this close count as one transfer node (same stop: 0 m)
TRANSFER_DETOUR = 1.3  # straight line -> street distance for transfer walks
TRANSFER_BUFFER_S = 60.0  # minimum slack at a transfer, on top of the average wait
WALK_SPEED_MS = 4.8 / 3.6
# stop-to-stop straight line -> distance travelled by the vehicle
RIDE_DETOUR = {"metro": 1.05, "bus": 1.2, "trolleybus": 1.2, "tram": 1.1}
# local service windows (hour of day, fractional); metro: OSM opening_hours Mo-Su 06:20-00:00
SERVICE_HOURS = {
    "metro": (6 + 20 / 60, 24.0),
    "bus": (6.0, 23.5),
    "trolleybus": (6.0, 23.5),
    "tram": (6.0, 23.5),
}
# The airport's published operating hours. OSM relation IDs distinguish night bus 3.
AIRPORT_DAY_RELATION = 3014420
AIRPORT_NIGHT_RELATION = 19593601
AIRPORT_SERVICE_HOURS = {
    AIRPORT_DAY_RELATION: (6.0, 23.0),
    AIRPORT_NIGHT_RELATION: (23.0, 6.0),
}
CACHE_TTL_S = 600.0
GRID_DEG = 0.004  # ~440 m lat / ~325 m lon at the region: cell >= TRANSFER_RADIUS_M


def hop_speed_boost(hop_m: float) -> float:
    """Commercial speed already includes dwell at ~400 m stop spacing; long non-stop hops (suburban
    sections) run faster: x1 up to 1 km, rising linearly to x2 at 3 km and beyond."""
    return 1.0 + min(1.0, max(0.0, (hop_m - 1000.0) / 2000.0))


# --- network ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Stop:
    idx: int
    id: str
    lat: float
    lon: float
    name_ru: Optional[str]
    name_en: Optional[str]
    name_kk: Optional[str]
    kind: str

    @property
    def point(self) -> Point:
        return (self.lat, self.lon)

    @property
    def name(self) -> Optional[str]:
        return self.name_ru or self.name_en or self.name_kk


@dataclass
class Route:
    idx: int
    id: str
    kind: str
    ref: Optional[str]
    name_ru: Optional[str]
    name_en: Optional[str]
    headway_min: float
    speed_kmh: float
    stops: List[int] = field(default_factory=list)  # stop idx in travel order
    inferred_reverse: bool = False  # synthetic opposite direction of a one-direction OSM relation
    cum_m: List[float] = field(default_factory=list)  # distance travelled up to stops[i]
    cum_s: List[float] = field(default_factory=list)  # riding time (no waiting) up to stops[i]
    osm_relation_id: Optional[int] = None

    def ride_s(self, p: int, q: int) -> float:
        return self.cum_s[q] - self.cum_s[p]


STOPS_SQL = """
SELECT id::text AS id, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon,
       name_ru, name_en, name_kk, kind
FROM transit_stops
WHERE id IN (SELECT stop_id FROM transit_route_stops)
ORDER BY id
"""
ROUTES_SQL = """
SELECT id::text AS id, kind, ref, name_ru, name_en, osm_relation_id,
       avg_headway_min::float8 AS headway, speed_kmh::float8 AS speed
FROM transit_routes
ORDER BY id
"""
ROUTE_STOPS_SQL = """
SELECT route_id::text AS route_id, stop_id::text AS stop_id
FROM transit_route_stops
ORDER BY route_id, ord
"""


class TransitNetwork:
    def __init__(self, stops: List[Stop], routes: List[Route]) -> None:
        self.stops = stops
        self.routes = routes
        # stop idx -> [(route idx, position in route)]
        self.by_stop: Dict[int, List[Tuple[int, int]]] = {}
        for r in routes:
            for pos, s in enumerate(r.stops):
                self.by_stop.setdefault(s, []).append((r.idx, pos))
        self._grid: Dict[Tuple[int, int], List[int]] = {}
        for s in stops:
            if s.idx in self.by_stop:
                self._grid.setdefault(self._cell(s.lat, s.lon), []).append(s.idx)
        self._neighbors: Dict[int, List[Tuple[int, float]]] = {}

    @staticmethod
    def _cell(lat: float, lon: float) -> Tuple[int, int]:
        return (int(math.floor(lat / GRID_DEG)), int(math.floor(lon / GRID_DEG)))

    @classmethod
    def build(cls, stop_rows: Sequence[dict], route_rows: Sequence[dict], rs_rows: Sequence[dict]):
        stops = [
            Stop(
                i,
                **{k: r[k] for k in ("id", "lat", "lon", "name_ru", "name_en", "name_kk", "kind")},
            )
            for i, r in enumerate(stop_rows)
        ]
        stop_ix = {s.id: s.idx for s in stops}
        routes = [
            Route(
                i,
                r["id"],
                r["kind"],
                r["ref"],
                r["name_ru"],
                r["name_en"],
                r["headway"],
                r["speed"],
                osm_relation_id=r.get("osm_relation_id"),
            )
            for i, r in enumerate(route_rows)
        ]
        route_ix = {r.id: r.idx for r in routes}
        for row in rs_rows:
            r = routes[route_ix[row["route_id"]]]
            r.stops.append(stop_ix[row["stop_id"]])
        routes = [r for r in routes if len(r.stops) >= 2]
        # OSM maps many lines as one relation only. A line with a single relation gets its
        # opposite direction inferred (same stops reversed; opposite-side stops are close enough).
        by_line: Dict[Tuple[str, str, bool], List[Route]] = {}
        for r in routes:
            if r.ref:
                by_line.setdefault(
                    (r.kind, r.ref, r.osm_relation_id == AIRPORT_NIGHT_RELATION), []
                ).append(r)
        for group in by_line.values():
            if len(group) == 1 and group[0].stops[0] != group[0].stops[-1]:
                g = group[0]
                routes.append(
                    Route(
                        len(routes),
                        g.id,
                        g.kind,
                        g.ref,
                        g.name_ru,
                        g.name_en,
                        g.headway_min,
                        g.speed_kmh,
                        g.stops[::-1],
                        inferred_reverse=True,
                        osm_relation_id=g.osm_relation_id,
                    )
                )
        for i, r in enumerate(routes):
            r.idx = i
            detour = RIDE_DETOUR.get(r.kind, 1.2)
            total, secs, cum, cum_t = 0.0, 0.0, [0.0], [0.0]
            for a, b in zip(r.stops, r.stops[1:]):
                hop = haversine_m(stops[a].point, stops[b].point) * detour
                total += hop
                secs += hop / (r.speed_kmh / 3.6 * hop_speed_boost(hop))
                cum.append(total)
                cum_t.append(secs)
            r.cum_m, r.cum_s = cum, cum_t
        return cls(stops, routes)

    @classmethod
    async def load(cls, conn) -> "TransitNetwork":
        stop_rows = await fetch_all(conn, STOPS_SQL)
        route_rows = await fetch_all(conn, ROUTES_SQL)
        rs_rows = await fetch_all(conn, ROUTE_STOPS_SQL)
        return cls.build(stop_rows, route_rows, rs_rows)

    def neighbors(
        self, stop_idx: int, radius_m: float = TRANSFER_RADIUS_M
    ) -> List[Tuple[int, float]]:
        """[(stop idx, straight-line metres)] within radius, including the stop itself (0 m)."""
        cached = self._neighbors.get(stop_idx)
        if cached is not None:
            return cached
        s = self.stops[stop_idx]
        ci, cj = self._cell(s.lat, s.lon)
        out = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for t in self._grid.get((ci + di, cj + dj), ()):
                    d = 0.0 if t == stop_idx else haversine_m(s.point, self.stops[t].point)
                    if d <= radius_m:
                        out.append((t, d))
        self._neighbors[stop_idx] = out
        return out

    def stops_near(self, p: Point, radius_m: float) -> List[Tuple[int, float]]:
        # linear scan: ~1k stops, cheaper and simpler than a second index
        out = []
        for idx in self.by_stop:
            d = haversine_m(p, self.stops[idx].point)
            if d <= radius_m:
                out.append((idx, d))
        return out


_cache: Dict[str, Any] = {"net": None, "at": 0.0}


async def get_network(conn, max_age_s: float = CACHE_TTL_S) -> TransitNetwork:
    """Process-wide cached network (reloaded after ``max_age_s``)."""
    now = time.monotonic()
    if _cache["net"] is None or now - _cache["at"] > max_age_s:
        _cache["net"] = await TransitNetwork.load(conn)
        _cache["at"] = now
    return _cache["net"]


def reset_network_cache() -> None:
    _cache["net"] = None


# --- results ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TransitLeg:
    type: str  # 'walk' | 'ride'
    duration_s: float  # for 'ride' includes the average wait (wait_s)
    distance_m: float
    from_point: Point
    to_point: Point
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    from_name_en: Optional[str] = None
    to_name_en: Optional[str] = None
    geometry: str = ""  # polyline6
    route_id: Optional[str] = None
    route_ref: Optional[str] = None
    kind: Optional[str] = None  # vehicle kind of a ride leg
    n_stops: int = 0
    wait_s: float = 0.0
    headway_min: Optional[float] = None


@dataclass(frozen=True)
class TransitOption:
    mode: str  # 'metro' | 'bus' (primary vehicle, see module doc)
    kind: str  # exact kind of the primary vehicle: metro/bus/trolleybus/tram
    duration_s: float
    transfers: int
    legs: List[TransitLeg]
    approximate: bool = True

    @property
    def refs(self) -> List[str]:
        return [leg.route_ref or "?" for leg in self.legs if leg.type == "ride"]

    @property
    def distance_m(self) -> float:
        return sum(leg.distance_m for leg in self.legs)

    @property
    def walk_m(self) -> float:
        return sum(leg.distance_m for leg in self.legs if leg.type == "walk")

    def to_dict(self) -> dict:
        from dataclasses import asdict

        d = asdict(self)
        d["refs"] = self.refs
        d["distance_m"] = self.distance_m
        return d


# --- search -------------------------------------------------------------------------------------


def _local_hour(depart: Optional[datetime]) -> Optional[float]:
    if depart is None:
        return None
    if depart.tzinfo is not None:
        try:
            depart = depart.astimezone(default_region().tz)
        except Exception:  # tzdata missing: keep the offset the caller gave
            pass
    return depart.hour + depart.minute / 60.0


def _in_service(route: Route, hour: Optional[float]) -> bool:
    if hour is None:
        return True
    start, end = AIRPORT_SERVICE_HOURS.get(
        route.osm_relation_id, SERVICE_HOURS.get(route.kind, (0.0, 24.0))
    )
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end


def _walk_leg(
    a: Point, b: Point, dur: float, dist: float, from_name=None, to_name=None
) -> TransitLeg:
    return TransitLeg(
        type="walk",
        duration_s=dur,
        distance_m=dist,
        from_point=a,
        to_point=b,
        from_name=from_name,
        to_name=to_name,
        geometry=encode_polyline6([a, b]),
    )


def _ride_leg(net: TransitNetwork, r: Route, p: int, q: int) -> TransitLeg:
    a, b = net.stops[r.stops[p]], net.stops[r.stops[q]]
    wait = r.headway_min * 30.0
    return TransitLeg(
        type="ride",
        duration_s=wait + r.ride_s(p, q),
        distance_m=r.cum_m[q] - r.cum_m[p],
        from_point=a.point,
        to_point=b.point,
        from_name=a.name,
        to_name=b.name,
        from_name_en=a.name_en,
        to_name_en=b.name_en,
        geometry=encode_polyline6([net.stops[s].point for s in r.stops[p : q + 1]]),
        route_id=r.id,
        route_ref=r.ref,
        kind=r.kind,
        n_stops=q - p,
        wait_s=wait,
        headway_min=r.headway_min,
    )


async def _candidates(net, router, p: Point, to_stop: bool, allowed, max_radius: float):
    """Nearest stop of every passing route within the radius, with real walking times.

    Returns {stop idx: (walk_s, walk_m)}. ``to_stop``: walk p -> stops, else stops -> p.
    """
    near = net.stops_near(p, max_radius)
    best_per_route: Dict[int, Tuple[float, int]] = {}
    for idx, d in near:
        for ridx, _ in net.by_stop[idx]:
            if ridx in allowed and (ridx not in best_per_route or d < best_per_route[ridx][0]):
                best_per_route[ridx] = (d, idx)
    ranked = sorted({idx: d for d, idx in best_per_route.values()}.items(), key=lambda kv: kv[1])
    idxs = [i for i, _ in ranked[:MAX_CANDIDATE_STOPS]]
    if not idxs:
        return {}
    pts = [net.stops[i].point for i in idxs]
    if to_stop:
        m = await router.matrix([p], pts, "walk")
        durs, dists = m.durations_s[0], m.distances_m[0]
    else:
        m = await router.matrix(pts, [p], "walk")
        durs, dists = [row[0] for row in m.durations_s], [row[0] for row in m.distances_m]
    out = {}
    for i, dur, dist in zip(idxs, durs, dists):
        if dur is not None and dist is not None and dist <= MAX_WALK_M:
            out[i] = (dur, dist)
    return out


async def find_transit_options(
    net: TransitNetwork,
    router: RoutingProvider,
    a: Point,
    b: Point,
    depart: Optional[datetime] = None,
    *,
    max_options: int = 4,
    drop_slower_than_walking: bool = True,
) -> List[TransitOption]:
    """Best transit itineraries A -> B (<= 1 transfer), fastest first, best of each mode kept.

    Options not faster than walking the whole way are dropped (``drop_slower_than_walking``), so an
    empty list can also mean "just walk". ``depart`` only matters for service hours (metro
    06:20-24:00, buses 06:00-23:30, local time;
    naive datetimes are taken as local). Returns [] if nothing is within walking range of both ends.
    """
    hour = _local_hour(depart)
    allowed = {r.idx for r in net.routes if _in_service(r, hour)}
    if not allowed:
        return []
    cand_a = await _candidates(net, router, a, True, allowed, MAX_WALK_RADIUS_M)
    cand_b = await _candidates(net, router, b, False, allowed, MAX_WALK_RADIUS_M)
    if not cand_a or not cand_b:
        return []

    # route idx -> [(pos, stop idx, walk_s, walk_m)] on the destination side
    b_by_route: Dict[int, List[Tuple[int, int, float, float]]] = {}
    for sidx, (wd, wm) in cand_b.items():
        for ridx, pos in net.by_stop[sidx]:
            if ridx in allowed:
                b_by_route.setdefault(ridx, []).append((pos, sidx, wd, wm))

    found: List[Tuple[float, tuple]] = []  # (total_s, description)

    for sa, (wa_s, _wa_m) in cand_a.items():
        for r1i, p in net.by_stop[sa]:
            if r1i not in allowed:
                continue
            r1 = net.routes[r1i]
            wait1 = r1.headway_min * 30.0
            head = wa_s + wait1
            # direct
            for q, sb, wb_s, _wb_m in b_by_route.get(r1i, ()):
                if q > p:
                    found.append((head + r1.ride_s(p, q) + wb_s, ("direct", sa, r1i, p, q, sb)))
            # one transfer: ride r1 to s, walk to t, ride r2 to the destination side
            for s_pos in range(p + 1, len(r1.stops)):
                s_idx = r1.stops[s_pos]
                t1 = head + r1.ride_s(p, s_pos)
                for t_idx, d_m in net.neighbors(s_idx):
                    walk_s = d_m * TRANSFER_DETOUR / WALK_SPEED_MS
                    for r2i, qpos in net.by_stop[t_idx]:
                        if r2i == r1i or r2i not in b_by_route:
                            continue
                        r2 = net.routes[r2i]
                        if r2.ref == r1.ref and r2.kind == r1.kind:
                            continue  # same line, other direction: pointless transfer
                        t2 = t1 + walk_s + TRANSFER_BUFFER_S + r2.headway_min * 30.0
                        for q, sb, wb_s, _wb_m in b_by_route[r2i]:
                            if q > qpos:
                                found.append(
                                    (
                                        t2 + r2.ride_s(qpos, q) + wb_s,
                                        (
                                            "transfer",
                                            sa,
                                            r1i,
                                            p,
                                            s_pos,
                                            t_idx,
                                            d_m,
                                            r2i,
                                            qpos,
                                            q,
                                            sb,
                                        ),
                                    )
                                )

    walk_s = None
    if drop_slower_than_walking:
        try:
            walk_s = (await router.route(a, b, "walk")).duration_s
        except RoutingError:  # too far to walk / engine problem: nothing to compare with
            walk_s = None
    if walk_s is not None:
        found = [f for f in found if f[0] < walk_s]
    found.sort(key=lambda x: x[0])
    chosen: List[TransitOption] = []
    seen_lines = set()
    pool: List[TransitOption] = []
    for _total, desc in found:
        key = _line_key(net, desc)
        if key in seen_lines:
            continue
        # a slower itinerary that merely adds lines to an already found one is not useful
        if any(set(prev) < set(key) for prev in seen_lines):
            continue
        seen_lines.add(key)
        pool.append(_materialize(net, a, b, cand_a, cand_b, desc))
        if len(pool) >= max(30, max_options * 6):
            break
    # best overall, then best of each other mode, then fastest of the rest
    for opt in pool:
        if len(chosen) >= max_options:
            break
        if opt.mode not in {c.mode for c in chosen}:
            chosen.append(opt)
    for opt in pool:
        if len(chosen) >= max_options:
            break
        if opt not in chosen:
            chosen.append(opt)
    chosen.sort(key=lambda o: o.duration_s)
    return chosen


def _line_key(net: TransitNetwork, desc: tuple) -> tuple:
    """Distinct itineraries = distinct sequence of lines (ref+kind); other stops are variants."""
    r1 = net.routes[desc[2]]
    if desc[0] == "direct":
        return ((r1.kind, r1.ref),)
    r2 = net.routes[desc[7]]
    return ((r1.kind, r1.ref), (r2.kind, r2.ref))


def _materialize(net, a: Point, b: Point, cand_a, cand_b, desc: tuple) -> TransitOption:
    legs: List[TransitLeg] = []
    sa = desc[1]
    wa_s, wa_m = cand_a[sa]
    legs.append(_walk_leg(a, net.stops[sa].point, wa_s, wa_m, to_name=net.stops[sa].name))
    if desc[0] == "direct":
        _, _, r1i, p, q, sb = desc
        legs.append(_ride_leg(net, net.routes[r1i], p, q))
        transfers = 0
    else:
        _, _, r1i, p, s_pos, t_idx, d_m, r2i, qpos, q, sb = desc
        r1, r2 = net.routes[r1i], net.routes[r2i]
        legs.append(_ride_leg(net, r1, p, s_pos))
        s_stop, t_stop = net.stops[r1.stops[s_pos]], net.stops[t_idx]
        if d_m > 0:
            legs.append(
                _walk_leg(
                    s_stop.point,
                    t_stop.point,
                    d_m * TRANSFER_DETOUR / WALK_SPEED_MS,
                    d_m * TRANSFER_DETOUR,
                    s_stop.name,
                    t_stop.name,
                )
            )
        legs.append(_ride_leg(net, r2, qpos, q))
        transfers = 1
    wb_s, wb_m = cand_b[sb]
    legs.append(_walk_leg(net.stops[sb].point, b, wb_s, wb_m, from_name=net.stops[sb].name))
    duration = sum(leg.duration_s for leg in legs)
    if transfers:
        duration += TRANSFER_BUFFER_S
    rides = [leg for leg in legs if leg.type == "ride"]
    primary = max(rides, key=lambda leg: leg.duration_s - leg.wait_s)
    return TransitOption(
        mode="metro" if primary.kind == "metro" else "bus",
        kind=primary.kind or "bus",
        duration_s=round(duration, 1),
        transfers=transfers,
        legs=legs,
    )
