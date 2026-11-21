"""Reverse geocoding from our own data only (Ш-23c, SSOT §6.1, §13). Public, read-only.

Order of the answer for a tapped point: the nearest place of our database within PLACE_RADIUS_M,
else the nearest address/named building of `osm_addresses` within ADDRESS_RADIUS_M, else the bare
point. No external geocoder is ever called (Nominatim's usage policy forbids heavy app use).
Buildings are stored as one point (the centroid of the way), so the address radius is wider than
the place radius: a tap inside a big building can be some tens of metres from its centroid.
"""

from typing import Any, Dict

from fastapi import APIRouter, Query, Request, Response

from app.clientip import client_ip
from app.db import fetch_one
from app.errors import AppError
from app.i18n import pick_locale
from app.places import service
from app.places import sql as places_sql
from app.places.api import _summary
from app.ratelimit import acquire_own

router = APIRouter(prefix="/v1/geocode", tags=["geocode"])

# Same bbox as the OSM places import (data/osm/import_places.py BBOX): Almaty and its mountains.
WEST, SOUTH, EAST, NORTH = 76.70, 43.00, 77.20, 43.45
PLACE_RADIUS_M = 30
ADDRESS_RADIUS_M = 50
LIMIT_PER_MINUTE = 120  # per client address; a tap is one request, a dragged pin is debounced
CACHE_SECONDS = 300  # the data changes at import time only

NEAREST_PLACE = (
    "SELECT"
    + places_sql._SUMMARY_COLS
    + """,
       ST_Distance(p.geom, pt.g) AS distance_m
FROM (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography AS g) pt
JOIN places p ON ST_DWithin(p.geom, pt.g, %(radius)s)
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.status = 'active'
ORDER BY ST_Distance(p.geom, pt.g), p.popularity DESC, p.id
LIMIT 1
"""
)

# An address needs a street and a number, or at least a building name.
NEAREST_ADDRESS = """
SELECT a.housenumber, a.street_ru, a.street_en, a.street_kk, a.name_ru, a.name_en, a.name_kk,
       ST_Y(a.geom::geometry) AS lat, ST_X(a.geom::geometry) AS lon,
       ST_Distance(a.geom, pt.g) AS distance_m
FROM (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography AS g) pt
JOIN osm_addresses a ON ST_DWithin(a.geom, pt.g, %(radius)s)
WHERE (a.housenumber IS NOT NULL AND coalesce(a.street_ru, a.street_en, a.street_kk) IS NOT NULL)
   OR coalesce(a.name_ru, a.name_en, a.name_kk) IS NOT NULL
ORDER BY ST_Distance(a.geom, pt.g), a.osm_type, a.osm_id
LIMIT 1
"""


def address_text(row: Dict[str, Any], locale: str):
    street, _ = service.pick_text(row, "street", locale)
    number = row["housenumber"]
    if street and number:
        return "%s %s" % (street, number)
    return None


@router.get("/reverse")
async def reverse(
    request: Request,
    response: Response,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> Dict[str, Any]:
    if not (WEST <= lon <= EAST and SOUTH <= lat <= NORTH):
        raise AppError(422, "validation_error", "The point is outside Almaty")
    wait = await acquire_own(
        request.app.state.db, [(request.app.state.geocode_limiter, client_ip(request))]
    )
    if wait:
        raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)})

    locale = pick_locale(request.headers.get("accept-language"))
    params = {"lat": lat, "lon": lon}
    async with request.app.state.db.transaction() as conn:
        place = await fetch_one(conn, NEAREST_PLACE, {**params, "radius": PLACE_RADIUS_M})
        address = None
        if place is None:
            address = await fetch_one(conn, NEAREST_ADDRESS, {**params, "radius": ADDRESS_RADIUS_M})
    response.headers["Cache-Control"] = "public, max-age=%d" % CACHE_SECONDS

    if place is not None:
        return {
            "kind": "place",
            "place": _summary(place, locale),
            "lat": lat,
            "lon": lon,
            "distance_m": round(place["distance_m"]),
        }
    if address is not None:
        name, _ = service.pick_text(address, "name", locale)
        return {
            "kind": "address",
            "address": address_text(address, locale),
            "name": name,
            "lat": address["lat"],  # the building point: a sound routing target
            "lon": address["lon"],
            "distance_m": round(address["distance_m"]),
        }
    return {"kind": "point", "lat": lat, "lon": lon}
