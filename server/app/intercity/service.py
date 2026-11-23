"""Intercity options: hub links from the database plus road modes from the router.

Door to door = access to the departure hub + buffer (check-in) + the ride + egress from the arrival
hub. Waiting for the next departure is NOT included: schedules are unknown (OPEN(SSOT §16.15)).
Prices are per person for plane/train/bus/tour and per vehicle for car/taxi (`price_basis`).
"""

import asyncio
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db import fetch_all, fetch_one
from app.routing.base import NoRoute, Point, RoutingProvider
from app.routing.costs import IntercityParams, Tariff, calculate_cost, recommend
from app.routing.fake import haversine_m
from app.routing.service import _traffic_max

LINKS_BETWEEN = """
SELECT l.mode, l.duration_min_min, l.duration_max_min, l.price_kzt_min, l.price_kzt_max,
       l.transfers, l.buffer_min, l.schedule_days, l.departure_hint, l.note_ru, l.note_en,
       l.source, l.source_url, l.as_of, l.approximate,
       f.id AS from_id, f.name_ru AS from_name_ru, f.name_en AS from_name_en,
       ST_Y(f.location) AS from_lat, ST_X(f.location) AS from_lon,
       t.id AS to_id, t.name_ru AS to_name_ru, t.name_en AS to_name_en,
       ST_Y(t.location) AS to_lat, ST_X(t.location) AS to_lon
FROM intercity_links l
JOIN intercity_hubs f ON f.id = l.from_hub
JOIN intercity_hubs t ON t.id = l.to_hub
WHERE ST_DWithin(f.location::geography,
                 ST_SetSRID(ST_MakePoint(%(from_lon)s, %(from_lat)s), 4326)::geography,
                 f.catchment_km * 1000)
  AND ST_DWithin(t.location::geography,
                 ST_SetSRID(ST_MakePoint(%(to_lon)s, %(to_lat)s), 4326)::geography,
                 t.catchment_km * 1000)
ORDER BY l.id
"""

SETTINGS = "SELECT key, source, as_of FROM intercity_settings"
INTERCITY_TARIFF = """
SELECT source, created_at::date AS as_of
FROM transport_tariffs
WHERE mode = 'taxi_intercity' AND valid_from <= %s
ORDER BY valid_from DESC, version_id DESC
LIMIT 1
"""


def _pick(row: Dict[str, Any], base: str, locale: str) -> Optional[str]:
    return row.get("%s_%s" % (base, "ru" if locale == "ru" else "en")) or row.get("%s_ru" % base)


async def _drive(router: RoutingProvider, a: Point, b: Point) -> Tuple[float, float, Optional[str]]:
    """(duration_s, distance_m, geometry) by car; a straight-line guess if the points coincide."""
    try:
        result = await router.route(a, b, "car")
    except NoRoute:
        metres = haversine_m(a, b)
        return metres / 8.0, metres, None  # ~30 km/h on a detour-free guess; only for tiny hops
    return result.duration_s, result.distance_m, result.geometry


def _taxi_leg_cost(taxi: Optional[Tariff], distance_m: float, duration_s: float, factor: float):
    if taxi is None:
        return None, None
    return calculate_cost(taxi, distance_m, duration_s, factor)


def _sum(*values: Optional[int]) -> Optional[int]:
    return None if any(v is None for v in values) else sum(values)  # type: ignore[arg-type]


async def intercity_options(
    conn,
    router: RoutingProvider,
    tariffs: Dict[str, Tariff],
    params: IntercityParams,
    origin: Point,
    target: Point,
    travel_date: Optional[date],
    locale: str,
    now: datetime,
) -> List[Dict[str, Any]]:
    """Options for one pair of points, fastest first; `recommended` marks one of them.

    Raises RoutingUnavailable when the router is down (the caller answers 503)."""
    if haversine_m(origin, target) < params.min_distance_km * 1000:
        return []  # not an intercity trip: the ordinary directions cover it
    factor = _traffic_max(now)
    city_taxi = tariffs.get("taxi")
    options: List[Dict[str, Any]] = []

    rows = await fetch_all(
        conn,
        LINKS_BETWEEN,
        {"from_lat": origin[0], "from_lon": origin[1], "to_lat": target[0], "to_lon": target[1]},
    )
    drives: Dict[Tuple[Point, Point], Tuple[float, float, Optional[str]]] = {}
    pairs = set()
    for row in rows:
        pairs.add((origin, (row["from_lat"], row["from_lon"])))
        pairs.add(((row["to_lat"], row["to_lon"]), target))
    ordered = sorted(pairs)
    for pair, result in zip(ordered, await asyncio.gather(*[_drive(router, *p) for p in ordered])):
        drives[pair] = result

    best: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        a_s, a_m, _ = drives[(origin, (row["from_lat"], row["from_lon"]))]
        e_s, e_m, _ = drives[((row["to_lat"], row["to_lon"]), target)]
        buffer_s = row["buffer_min"] * 60
        main_min, main_max = row["duration_min_min"] * 60, row["duration_max_min"] * 60
        a_low, a_high = _taxi_leg_cost(city_taxi, a_m, a_s, factor)
        if row["mode"] == "tour":
            e_low = e_high = 0  # the tour carries the group on from its meeting point
        else:
            e_low, e_high = _taxi_leg_cost(city_taxi, e_m, e_s, factor)
        price_min, price_max = row["price_kzt_min"], row["price_kzt_max"]
        total_min = a_s + buffer_s + main_min + e_s
        total_max = a_s * factor + buffer_s + main_max + e_s * factor
        legs = [
            _leg("access", "taxi", None, _pick(row, "from_name", locale), a_s, a_s * factor, a_m)
            | _cost(a_low, a_high),
        ]
        if buffer_s:
            legs.append(
                _leg("wait", None, None, _pick(row, "from_name", locale), buffer_s, buffer_s)
            )
        legs.append(
            _leg(
                "main",
                row["mode"],
                _pick(row, "from_name", locale),
                _pick(row, "to_name", locale),
                main_min,
                main_max,
            )
            | _cost(price_min, price_max)
        )
        legs.append(
            _leg(
                "egress",
                "tour" if row["mode"] == "tour" else "taxi",
                _pick(row, "to_name", locale),
                None,
                e_s,
                e_s * factor,
                e_m,
            )
            | _cost(e_low, e_high)
        )
        days = row["schedule_days"]
        option = {
            "mode": row["mode"],
            "duration_s": round((total_min + total_max) / 2),
            "duration_s_min": round(total_min),
            "duration_s_max": round(total_max),
            "cost_kzt_min": _sum(a_low, price_min, e_low),
            "cost_kzt_max": _sum(a_high, price_max, e_high),
            "price_basis": "person",
            "approximate": bool(row["approximate"]),
            "source": row["source"],
            "source_url": row["source_url"],
            "as_of": row["as_of"].isoformat(),
            "transfers": row["transfers"],
            "schedule": {
                "days": list(days) if days is not None else None,
                "departure_hint": row["departure_hint"],
                "runs_on_date": (travel_date.isoweekday() in days)
                if (days is not None and travel_date is not None)
                else None,
            },
            "note": _pick(row, "note", locale),
            "legs": legs,
            "geometry": None,
        }
        kept = best.get(row["mode"])
        if kept is None or option["duration_s"] < kept["duration_s"]:
            best[row["mode"]] = option
    options.extend(best.values())
    options.extend(await _road_options(conn, router, tariffs, params, origin, target, now))

    options.sort(key=lambda o: (o["duration_s"], o["mode"]))
    priced = [o for o in options if o["cost_kzt_max"] is not None]
    index = recommend(priced)
    for o in options:
        o["recommended"] = False
    if index is not None:
        priced[index]["recommended"] = True
    return options


def _leg(kind, mode, from_name, to_name, dur_min, dur_max, distance_m=None) -> Dict[str, Any]:
    return {
        "type": kind,
        "mode": mode,
        "from_name": from_name,
        "to_name": to_name,
        "duration_s_min": round(dur_min),
        "duration_s_max": round(dur_max),
        "distance_m": round(distance_m) if distance_m is not None else None,
    }


def _cost(low: Optional[int], high: Optional[int]) -> Dict[str, Any]:
    return {"cost_kzt_min": low, "cost_kzt_max": high}


async def _road_options(conn, router, tariffs, params, origin, target, now) -> List[Dict[str, Any]]:
    try:
        result = await router.route(origin, target, "car")
    except NoRoute:
        return []
    if (
        result.distance_m > params.max_road_km * 1000
        or result.distance_m < params.min_distance_km * 1000
    ):
        return []
    settings = {r["key"]: r for r in await fetch_all(conn, SETTINGS, ())}
    fuel = [settings[k] for k in ("fuel_l_per_100km", "fuel_price_kzt_per_l") if k in settings]
    car_low, car_high = calculate_cost(
        params.own_car_tariff(), result.distance_m, result.duration_s, 1.0
    )
    common = {
        "duration_s": round(result.duration_s),
        "duration_s_min": round(result.duration_s),
        "duration_s_max": round(result.duration_s),
        "price_basis": "vehicle",
        "approximate": True,
        "source_url": None,
        "transfers": 0,
        "schedule": None,
        "note": None,
        "geometry": result.geometry,
        "distance_m": round(result.distance_m),
    }
    out = [
        {
            **common,
            "mode": "car",
            "cost_kzt_min": car_low,
            "cost_kzt_max": car_high,
            "source": "Valhalla (время, расстояние) + топливо по параметрам: %s"
            % "; ".join(f["source"] for f in fuel),
            "as_of": max((f["as_of"] for f in fuel), default=now.date()).isoformat(),
            "legs": [
                _leg(
                    "main",
                    "car",
                    None,
                    None,
                    result.duration_s,
                    result.duration_s,
                    result.distance_m,
                )
                | _cost(car_low, car_high)
            ],
        }
    ]
    taxi = tariffs.get("taxi_intercity") or tariffs.get("taxi")
    if taxi is not None:
        info = await fetch_one(conn, INTERCITY_TARIFF, (now.date(),))
        low, high = calculate_cost(taxi, result.distance_m, result.duration_s, 1.0)
        # intercity per-km tariff has no minute component; a city fallback keeps its minutes
        out.append(
            {
                **common,
                "mode": "taxi",
                "cost_kzt_min": low,
                "cost_kzt_max": high,
                "source": "Valhalla (время, расстояние) + "
                + (info["source"] if info else "тариф такси"),
                "as_of": (info["as_of"] if info else now.date()).isoformat(),
                "legs": [
                    _leg(
                        "main",
                        "taxi",
                        None,
                        None,
                        result.duration_s,
                        result.duration_s,
                        result.distance_m,
                    )
                    | _cost(low, high)
                ],
            }
        )
    return out
