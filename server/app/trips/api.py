"""Trips API (prefix /v1, bearer auth; a user sees only their own trips).

    POST /trips/{id}/budget-choice   {"choice": "drop_places" | "cheaper" | "keep"}
        -> {"trip_id", "version", "budget": {...}}

Only Ш-35 lives here; the read endpoints (`GET /trips`, `GET /trips/{id}`) are Ш-37.

The planner stores two alternatives next to a plan that does not fit the budget (SSOT §5.2,
TECH_PLAN §2 working default of §16.3: show both, the person chooses). The choice makes one of
them the plan: the variant's days become the trip's days, `version` grows by one, the other
variant is deleted. `keep` accepts the plan as it is. 409 `budget_choice_unavailable` when the
plan fits the budget or a choice was already made; 404 for a missing or foreign trip.
`budget` is the stored block (no place ids): `status`, `total_kzt`, `breakdown`, `choice`, ...
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.auth import sessions
from app.auth.api import bearer_token
from app.errors import AppError
from app.trips import store

router = APIRouter(prefix="/v1", tags=["trips"])


class BudgetChoice(BaseModel):
    choice: Literal["drop_places", "cheaper", "keep"]


@router.post("/trips/{trip_id}/budget-choice")
async def budget_choice(trip_id: UUID, payload: BudgetChoice, request: Request):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        trip = await store.get_trip_for_update(conn, user["id"], trip_id)
        if trip is None:
            raise AppError(404, "not_found")
        budget = trip["budget"]
        if trip["budget_choice"] is not None or not budget.get("variants"):
            raise AppError(409, "budget_choice_unavailable")
        new_budget = await store.apply_budget_choice(conn, trip, payload.choice)
        version = trip["version"] + 1
    return {"trip_id": str(trip_id), "version": version, "budget": new_budget}
