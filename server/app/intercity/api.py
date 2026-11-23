"""`GET /v1/intercity/options`: ways to travel between two distant points (Ш-60). Public."""

from datetime import date, datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Query, Request
from psycopg import OperationalError

from app.clientip import client_ip
from app.errors import AppError
from app.i18n import pick_locale
from app.intercity.service import intercity_options
from app.ratelimit import RateRule, acquire_own
from app.regions import region_for_point
from app.routing import RoutingUnavailable
from app.routing.costs import load_intercity_params, load_tariffs

router = APIRouter(prefix="/v1/intercity", tags=["intercity"])

LIMIT_PER_MINUTE = 60  # per client address (a directions-like request: several router calls)
CACHE_SECONDS = 300


def make_limiter() -> RateRule:
    return RateRule("intercity", LIMIT_PER_MINUTE, 60)


@router.get("/options")
async def options(
    request: Request,
    from_lat: float = Query(..., ge=-90, le=90),
    from_lon: float = Query(..., ge=-180, le=180),
    to_lat: float = Query(..., ge=-90, le=90),
    to_lon: float = Query(..., ge=-180, le=180),
    date_: Annotated[Optional[date], Query(alias="date")] = None,
):
    db = request.app.state.db
    origin, target = (from_lat, from_lon), (to_lat, to_lon)
    try:
        async with db.transaction() as conn:
            origin_region = await region_for_point(conn, *origin)
            target_region = await region_for_point(conn, *target)
    except OperationalError:
        raise AppError(503, "db_unavailable") from None
    if origin_region is None or target_region is None:
        raise AppError(422, "validation_error", "The point is outside every region")
    wait = await acquire_own(db, [(request.app.state.intercity_limiter, client_ip(request))])
    if wait:
        raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)})

    locale = pick_locale(request.headers.get("accept-language"))
    now = datetime.now(origin_region.tz)
    try:
        async with db.transaction() as conn:
            tariffs = await load_tariffs(conn, (date_ or now.date()))
            params = await load_intercity_params(conn)
            if params is None:
                raise AppError(503, "routing_unavailable", "Intercity data is not loaded")
            found = await intercity_options(
                conn,
                request.app.state.routing_provider,
                tariffs,
                params,
                origin,
                target,
                date_,
                locale,
                now,
            )
    except OperationalError:
        raise AppError(503, "db_unavailable") from None
    except RoutingUnavailable:
        raise AppError(503, "routing_unavailable") from None
    return {
        "from": {"lat": from_lat, "lon": from_lon, "region": origin_region.id},
        "to": {"lat": to_lat, "lon": to_lon, "region": target_region.id},
        "date": date_.isoformat() if date_ else None,
        "options": found,
    }
