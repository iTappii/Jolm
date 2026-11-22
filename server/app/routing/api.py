"""Public directions endpoint inside the region."""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from pydantic import ValidationError

from app.db import fetch_one
from app.errors import AppError
from app.regions import default_region
from app.routing import RoutingUnavailable, get_network
from app.routing.costs import load_tariffs
from app.routing.schemas import DirectionOption, DirectionsRequest, RoutePoint
from app.routing.service import get_directions
from app.routing.sql import DESTINATION_BY_ID

log = logging.getLogger("app.routing")
router = APIRouter(prefix="/v1")


@router.post("/directions", response_model=List[DirectionOption])
async def directions(payload: DirectionsRequest, request: Request):
    db = request.app.state.db
    destination = payload.to
    if destination is None:
        try:
            async with db.transaction() as conn:
                row = await fetch_one(conn, DESTINATION_BY_ID, (payload.to_place_id,))
        except OperationalError:
            raise AppError(503, "db_unavailable") from None
        if row is None:
            raise AppError(404, "not_found")
        try:
            destination = RoutePoint.model_validate(row)
        except ValidationError:
            raise AppError(422, "validation_error") from None

    region = default_region()
    if not (
        region.contains(*payload.origin.as_point()) and region.contains(*destination.as_point())
    ):
        raise AppError(422, "validation_error")  # a point outside the region: no routing there yet

    try:
        depart_at = (
            payload.depart_at.astimezone(default_region().tz)
            if payload.depart_at is not None
            else datetime.now(default_region().tz)
        )
    except OverflowError:
        raise AppError(422, "validation_error") from None
    tariffs = {}
    network = None
    data_unavailable = False
    try:
        async with db.transaction() as conn:
            tariffs = await load_tariffs(conn, depart_at.date())
            if "bus" in tariffs or "metro" in tariffs:
                network = await get_network(conn)
    except OperationalError:
        log.warning("directions data unavailable", exc_info=True)
        data_unavailable = True

    try:
        options = await get_directions(
            request.app.state.routing_provider,
            network,
            tariffs,
            payload.origin.as_point(),
            destination.as_point(),
            depart_at,
            data_unavailable=data_unavailable,
        )
    except RoutingUnavailable:
        raise AppError(503, "routing_unavailable") from None
    body = []
    for option in options:
        item = option.model_dump(mode="json", exclude_none=True)
        item["congestion"] = None  # OPEN(SSOT §16.14): always present, always null for now
        body.append(item)
    return JSONResponse(body)
