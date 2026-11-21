"""Assemble available, priced directions options from the router and transit network."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from app.routing.base import NoRoute, Point, RouteResult, RoutingProvider, RoutingUnavailable
from app.routing.costs import Tariff, calculate_cost, recommend
from app.routing.fake import FakeRouter, encode_polyline6, haversine_m
from app.routing.geometry import decode_polyline6
from app.routing.schemas import DirectionOption, DirectionStep, Mode
from app.routing.transit import TransitNetwork, TransitOption, find_transit_options

log = logging.getLogger("app.routing")

# Five kilometres limits the standalone walk to about an hour at city walking pace.
MAX_WALK_M = 5000
ALMATY_TZ = ZoneInfo("Asia/Almaty")


def _traffic_max(depart_at: datetime) -> float:
    local = depart_at.astimezone(ALMATY_TZ)
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


async def get_directions(
    router: RoutingProvider,
    network: Optional[TransitNetwork],
    tariffs: Dict[str, Tariff],
    origin: Point,
    destination: Point,
    depart_at: datetime,
    *,
    data_unavailable: bool = False,
) -> List[DirectionOption]:
    road_modes = {}
    if haversine_m(origin, destination) <= MAX_WALK_M:
        road_modes["walk"] = ("walk",)
    if "scooter" in tariffs:
        road_modes["scooter"] = ("scooter",)
    motor_modes = tuple(mode for mode in ("taxi", "car") if mode in tariffs)
    if motor_modes:
        road_modes["car"] = motor_modes

    jobs = {mode: router.route(origin, destination, mode) for mode in road_modes}
    if network is not None and ("bus" in tariffs or "metro" in tariffs):
        jobs["transit"] = find_transit_options(
            network, router, origin, destination, depart_at, drop_slower_than_walking=False
        )
    results = await asyncio.gather(*jobs.values(), return_exceptions=True)

    options: List[DirectionOption] = []
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
                        options.append(option)
            continue
        if mode == "walk":
            if result.distance_m > MAX_WALK_M:
                continue
            walk_s = result.duration_s
        for public_mode in road_modes[mode]:
            tariff = None if public_mode == "walk" else tariffs[public_mode]
            options.append(_road_option(result, public_mode, tariff, offline, traffic_max))

    if not options and data_unavailable:
        raise RoutingUnavailable("directions unavailable")
    index = recommend(
        [option.model_dump(include={"mode", "duration_s", "cost_kzt_max"}) for option in options]
    )
    if index is not None:
        options[index].recommended = True
    return options
