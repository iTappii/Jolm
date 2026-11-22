"""Assemble available, priced directions options from the router and transit network."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.regions import default_region
from app.routing.base import NoRoute, Point, RouteResult, RoutingProvider, RoutingUnavailable
from app.routing.costs import Tariff, calculate_cost, recommend
from app.routing.fake import FakeRouter, encode_polyline6, haversine_m
from app.routing.geometry import decode_polyline6
from app.routing.schemas import DirectionOption, DirectionStep, Mode, group_of
from app.routing.transit import TransitNetwork, TransitOption, find_transit_options

log = logging.getLogger("app.routing")

# Five kilometres limits the standalone walk to about an hour at city walking pace.
MAX_WALK_M = 5000
# Ш-22a: up to this many path variants per transport group (variant 0 = the optimal one).
MAX_VARIANTS = 3
# A variant slower than this multiple of its group's best is not a reasonable alternative.
ALT_MAX_RATIO = 1.6
# Variants closer than this to a kept one (both duration and distance) are the same path.
NEAR_IDENTICAL = 0.03
# Ш-22a coordinator: two routes whose shapes stay within this distance of each other (the larger
# of the floor and the share of the longer route's length) are the same path, whatever the
# timings say. Measured as a discrete Hausdorff distance over resampled points.
SAME_PATH_FLOOR_M = 80.0
SAME_PATH_SHARE = 0.02
PATH_SAMPLES = 24


def _traffic_max(depart_at: datetime) -> float:
    local = depart_at.astimezone(default_region().tz)
    peak = 7 <= local.hour < 10 or 17 <= local.hour < 20
    return 1.6 if local.weekday() < 5 and peak else 1.25


def _road_option(
    result: RouteResult, mode: Mode, tariff: Optional[Tariff], offline: bool, traffic_max: float
) -> DirectionOption:
    motor = mode in ("taxi", "car")
    factor = traffic_max if motor else 1.0
    low, high = (
        calculate_cost(
            tariff,
            result.distance_m,
            result.duration_s,
            traffic_max=factor,
        )
        if tariff is not None
        else (0, 0)
    )
    steps = [
        DirectionStep(
            type="maneuver",
            instruction=m.instruction,
            duration_s=m.duration_s,
            distance_m=m.length_m,
            geometry=m.geometry,
        )
        for m in result.maneuvers
        if m.geometry
    ]
    return DirectionOption(
        mode=mode,
        duration_s=result.duration_s,
        duration_s_min=result.duration_s if motor else None,
        duration_s_max=round(result.duration_s * factor, 1) if motor else None,
        distance_m=result.distance_m,
        cost_kzt_min=low,
        cost_kzt_max=high,
        geometry=result.geometry,
        steps=steps or None,
        approximate=offline or motor or mode == "scooter" or bool(tariff and tariff.approximate),
    )


def _transit_option(result: TransitOption, tariffs: Dict[str, Tariff]) -> Optional[DirectionOption]:
    points: List[Point] = []
    steps: List[DirectionStep] = []
    low = high = 0
    approximate = result.approximate
    for leg in result.legs:
        if leg.type == "ride":
            # The surface-transit fare applies to bus, trolleybus, and tram.
            tariff = tariffs.get("metro" if leg.kind == "metro" else "bus")
            if tariff is None:
                return None
            leg_low, leg_high = calculate_cost(tariff, leg.distance_m, leg.duration_s)
            low += leg_low
            high += leg_high
            approximate = approximate or tariff.approximate
        leg_points = decode_polyline6(leg.geometry)
        if points and leg_points and points[-1] == leg_points[0]:
            leg_points = leg_points[1:]
        points.extend(leg_points)
        steps.append(
            DirectionStep(
                type=leg.type,
                duration_s=leg.duration_s,
                distance_m=leg.distance_m,
                geometry=leg.geometry,
                from_name=leg.from_name,
                to_name=leg.to_name,
                from_name_en=leg.from_name_en,
                to_name_en=leg.to_name_en,
                route_id=leg.route_id,
                route_ref=leg.route_ref,
                kind=leg.kind,
                n_stops=leg.n_stops if leg.type == "ride" else None,
                wait_s=leg.wait_s if leg.type == "ride" else None,
            )
        )
    return DirectionOption(
        mode=result.mode,
        duration_s=result.duration_s,
        distance_m=result.distance_m,
        cost_kzt_min=low,
        cost_kzt_max=high,
        geometry=encode_polyline6(points),
        steps=steps,
        approximate=approximate,
    )


def _rank(option: DirectionOption) -> float:
    """The "reasonable" metric that orders variants inside a group: time plus 1 second per tenge
    of the upper cost (the same trade-off `recommend` uses), so variant 0 is what it would pick."""
    return option.duration_s + option.cost_kzt_max


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= NEAR_IDENTICAL * max(a, b, 1.0)


def _resample(points: List[Point], count: int) -> List[Point]:
    """`count` points spread evenly along the path by length (straight segments)."""
    if len(points) < 2:
        return list(points) * count if points else []
    cumulative = [0.0]
    for a, b in zip(points, points[1:]):
        cumulative.append(cumulative[-1] + haversine_m(a, b))
    total = cumulative[-1]
    out: List[Point] = []
    index = 0
    for k in range(count):
        target = total * k / (count - 1)
        while index < len(points) - 2 and cumulative[index + 1] < target:
            index += 1
        span = cumulative[index + 1] - cumulative[index]
        t = (target - cumulative[index]) / span if span > 0 else 0.0
        a, b = points[index], points[index + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def path_distance_m(a: str, b: str) -> Optional[float]:
    """Discrete Hausdorff distance between two polyline6 paths over `PATH_SAMPLES` points each
    (the largest gap from a point of one path to the nearest point of the other). None when a
    path cannot be decoded."""
    try:
        first = _resample(decode_polyline6(a), PATH_SAMPLES)
        second = _resample(decode_polyline6(b), PATH_SAMPLES)
    except ValueError:
        return None
    if not first or not second:
        return None

    def directed(src: List[Point], dst: List[Point]) -> float:
        return max(min(haversine_m(p, q) for q in dst) for p in src)

    return max(directed(first, second), directed(second, first))


def same_path(a: RouteResult, b: RouteResult) -> bool:
    """True when the two routes follow practically the same streets."""
    gap = path_distance_m(a.geometry, b.geometry)
    return gap is not None and gap <= max(
        SAME_PATH_FLOOR_M, SAME_PATH_SHARE * max(a.distance_m, b.distance_m)
    )


def _distinct_routes(results: List[RouteResult]) -> List[RouteResult]:
    """Drop alternatives that repeat a kept route (same shape, or the same time and length)
    or are far slower than the best one."""
    best = min(r.duration_s for r in results)
    kept: List[RouteResult] = []
    for r in results:
        if r.duration_s > best * ALT_MAX_RATIO:
            continue
        if any(
            r.geometry == k.geometry
            or (_near(r.duration_s, k.duration_s) and _near(r.distance_m, k.distance_m))
            or same_path(r, k)
            for k in kept
        ):
            continue
        kept.append(r)
    return kept


def _transit_key(option: DirectionOption) -> tuple:
    """Distinct itinerary = the sequence of lines ridden (kind + ref)."""
    return tuple((s.kind, s.route_ref) for s in option.steps or [] if s.type == "ride")


def _finish_group(options: List[DirectionOption], limit: int, per_mode: bool = False):
    """Order a group's options by `_rank`, drop duplicates, cap at `limit` and number them."""
    ordered = sorted(options, key=_rank)
    kept: List[DirectionOption] = []
    for o in ordered:
        if any(
            o.geometry == k.geometry
            or (o.mode == k.mode and _transit_key(o) and _transit_key(o) == _transit_key(k))
            for k in kept
        ):
            continue
        if per_mode and any(k.mode == o.mode for k in kept):
            continue
        kept.append(o)
    kept = kept[:limit] if not per_mode else kept
    return [o.model_copy(update={"variant": i}) for i, o in enumerate(kept)]


async def _routes(router, origin, destination, mode: str, variants: int) -> List[RouteResult]:
    if variants <= 1 or not hasattr(router, "routes"):
        return [await router.route(origin, destination, mode)]
    # one spare, so a duplicate the dedupe drops does not cost a variant
    return await router.routes(origin, destination, mode, variants)


async def get_directions(
    router: RoutingProvider,
    network: Optional[TransitNetwork],
    tariffs: Dict[str, Tariff],
    origin: Point,
    destination: Point,
    depart_at: datetime,
    *,
    data_unavailable: bool = False,
    variants: int = MAX_VARIANTS,
) -> List[DirectionOption]:
    """Flat list of options; several per group (walk/transit/taxi/scooter/car) when `variants`
    > 1, ordered by group and then by variant. `variants=1` is the planner's mode: one route per
    road mode and the best itinerary per public-transit mode (bus, metro)."""
    road_modes = {}
    if haversine_m(origin, destination) <= MAX_WALK_M:
        road_modes["walk"] = ("walk",)
    if "scooter" in tariffs:
        road_modes["scooter"] = ("scooter",)
    motor_modes = tuple(mode for mode in ("taxi", "car") if mode in tariffs)
    if motor_modes:
        road_modes["car"] = motor_modes

    jobs = {mode: _routes(router, origin, destination, mode, variants) for mode in road_modes}
    if network is not None and ("bus" in tariffs or "metro" in tariffs):
        jobs["transit"] = find_transit_options(
            network,
            router,
            origin,
            destination,
            depart_at,
            max_options=4 if variants <= 1 else max(4, variants * 2),
            drop_slower_than_walking=False,
        )
    results = await asyncio.gather(*jobs.values(), return_exceptions=True)

    groups: Dict[str, List[DirectionOption]] = {}
    walk_s = None
    offline = isinstance(router, FakeRouter)
    traffic_max = _traffic_max(depart_at)
    for mode, result in zip(jobs, results):
        if isinstance(result, NoRoute):
            continue
        if isinstance(result, RoutingUnavailable):
            log.warning("directions provider unavailable", extra={"mode": mode})
            data_unavailable = True
            continue
        if isinstance(result, BaseException):
            raise result
        if mode == "transit":
            for transit in result:
                if walk_s is None or transit.duration_s < walk_s:
                    option = _transit_option(transit, tariffs)
                    if option is not None:
                        groups.setdefault("transit", []).append(option)
            continue
        if mode == "walk":
            result = [r for r in result if r.distance_m <= MAX_WALK_M]
            if not result:
                continue
            walk_s = result[0].duration_s
        for r in _distinct_routes(list(result)):
            for public_mode in road_modes[mode]:
                tariff = None if public_mode == "walk" else tariffs[public_mode]
                groups.setdefault(group_of(public_mode), []).append(
                    _road_option(r, public_mode, tariff, offline, traffic_max)
                )

    options: List[DirectionOption] = []
    for group in ("walk", "scooter", "taxi", "car", "transit"):
        if group in groups:
            per_mode = group == "transit" and variants <= 1
            options.extend(_finish_group(groups[group], variants, per_mode=per_mode))
    if not options and data_unavailable:
        raise RoutingUnavailable("directions unavailable")
    base = depart_at if depart_at.tzinfo else depart_at.replace(tzinfo=default_region().tz)
    for option in options:
        # motor modes: the upper estimate (traffic), the person should not be told too early
        option.arrive_at = (
            (base + timedelta(seconds=option.duration_s_max or option.duration_s))
            .astimezone(default_region().tz)
            .isoformat(timespec="seconds")
        )
    best = [o for o in options if o.variant == 0 or variants <= 1]
    index = recommend([o.model_dump(include={"mode", "duration_s", "cost_kzt_max"}) for o in best])
    if index is not None:
        best[index].recommended = True
    return options
