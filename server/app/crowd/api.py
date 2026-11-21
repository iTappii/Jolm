"""Crowd reports (Ш-47, SSOT §7.3). Prefix /v1, bearer auth (guests get 401: the limits and
the "I am here" metric need a person; a guest could not be told from a script).

    POST /places/{id}/checkin  {"lat", "lon"}
    POST /places/{id}/crowd    {"lat", "lon", "level": "empty"|"normal"|"busy"}
        both -> {"recorded": bool, "distance_m": int}

- 422 `too_far_from_place`: the reported location is further than 200 m from the place.
- `recorded: false`: a repeat inside the window (check-in 30 min, report 2 h) is answered with 200
  and not stored. 429 `rate_limited`: 40 check-ins and reports per person per 24 hours.
- The location is used for the check and is not stored (only the distance).
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.auth import sessions
from app.auth.api import bearer_token
from app.crowd import service
from app.live import clock

router = APIRouter(prefix="/v1", tags=["crowd"])


class Where(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class CrowdReport(Where):
    level: Literal["empty", "normal", "busy"]


@router.post("/places/{place_id}/checkin")
async def checkin(place_id: UUID, payload: Where, request: Request, response: Response):
    access = bearer_token(request)
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await service.record(
            conn, user["id"], place_id, "checkin", payload.lat, payload.lon, None, clock.now()
        )


@router.post("/places/{place_id}/crowd")
async def report(place_id: UUID, payload: CrowdReport, request: Request, response: Response):
    access = bearer_token(request)
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await service.record(
            conn, user["id"], place_id, "crowd", payload.lat, payload.lon, payload.level,
            clock.now(),
        )  # fmt: skip
