"""Trips API (prefix /v1, bearer auth; a user sees only their own trips).

    GET  /trips?limit=&before=                       -> {"items": [trip summary]}     (Ш-37)
    GET  /trips/{id}                                 -> the whole plan                (Ш-37)
    POST /trips/{id}/legs/{leg_id}/mode  {"mode"}    -> chosen transport of a leg     (Ш-37)
    POST /trips/{id}/items/{item_id}/remove {"force"?}  -> edit result                (Ш-38)
    POST /trips/{id}/items/{item_id}/replace {...}      -> edit result                (Ш-38)
    GET  /trips/{id}/proposals                       -> {"items": [proposal]}         (Ш-40)
    POST /proposals/{id}/accept                      -> edit result + "proposal"      (Ш-40)
    POST /proposals/{id}/decline                     -> {"id", "status": "declined"}  (Ш-40)
    POST /trips/{id}/budget-choice   {"choice": "drop_places" | "cheaper" | "keep"}   (Ш-35)
        -> {"trip_id", "version", "budget": {...}}

Exact JSON of every response: docs/reviews/Ш-37-server.md and Ш-38.md. Names follow
Accept-Language. Only the plan (`variant = 'main'`) is shown as days; the over-budget variants
come with the budget section (`budget.variants`), see `trips.read`.

The planner stores two alternatives next to a plan that does not fit the budget (SSOT §5.2,
TECH_PLAN §2 working default of §16.3: show both, the person chooses). The choice makes one of
them the plan: the variant's days become the trip's days, `version` grows by one, the other
variant is deleted. `keep` accepts the plan as it is. 409 `budget_choice_unavailable` when the
plan fits the budget or a choice was already made; 404 for a missing or foreign trip.
`budget` is the stored block (no place ids): `status`, `total_kzt`, `breakdown`, `choice`, ...
"""

from datetime import datetime, timedelta
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.auth import sessions
from app.auth.api import bearer_token
from app.errors import AppError
from app.i18n import pick_locale
from app.live import clock
from app.live import proposals as live_proposals
from app.providers.weather import city_forecast
from app.routing import FakeRouter
from app.trips import edit, read, store

router = APIRouter(prefix="/v1", tags=["trips"])


class LegMode(BaseModel):
    mode: Literal["walk", "scooter", "bus", "metro", "taxi", "car"]


class RemoveItem(BaseModel):
    force: bool = False  # remove a must-have stop too


class ReplaceItem(BaseModel):
    place_id: Optional[UUID] = None
    category: Optional[str] = Field(None, min_length=1, max_length=64)
    query: Optional[str] = Field(None, min_length=2, max_length=100)
    force: bool = False


def _locale(request: Request) -> str:
    return pick_locale(request.headers.get("accept-language"))


def _router(request: Request) -> Any:
    return getattr(request.app.state, "routing_provider", None) or FakeRouter()


@router.get("/trips")
async def list_trips(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    before: Optional[datetime] = Query(None),  # noqa: B008  updated_at cursor of the last item
):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        rows = await store.list_trips(conn, user["id"], limit, before)
    return {"items": [read.summary_json(r) for r in rows]}


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: UUID, request: Request):
    access = bearer_token(request)
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        trip = await store.get_trip_row(conn, user["id"], trip_id)
        if trip is None:
            raise AppError(404, "not_found")
        items = await store.main_items(conn, trip_id)
        legs = await store.main_legs(conn, trip_id)
        variants = {}
        for kind in (trip["budget"] or {}).get("variants") or {}:
            variants[kind] = await store.variant_items(conn, trip_id, kind)
        lodging = await store.lodging_options(conn, trip_id)
    return read.trip_json(trip, items, legs, variants, lodging, locale)


@router.post("/trips/{trip_id}/legs/{leg_id}/mode")
async def set_leg_mode(trip_id: UUID, leg_id: UUID, payload: LegMode, request: Request):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await edit.set_leg_mode(conn, user["id"], trip_id, leg_id, payload.mode)


@router.post("/trips/{trip_id}/items/{item_id}/remove")
async def remove_item(
    trip_id: UUID, item_id: UUID, request: Request, payload: Optional[RemoveItem] = None
):
    access = bearer_token(request)
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await edit.remove_item(
            conn, _router(request), user["id"], trip_id, item_id, locale,
            force=bool(payload and payload.force),
        )  # fmt: skip


@router.post("/trips/{trip_id}/items/{item_id}/replace")
async def replace_item(trip_id: UUID, item_id: UUID, payload: ReplaceItem, request: Request):
    access = bearer_token(request)
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await edit.replace_item(
            conn, _router(request), user["id"], trip_id, item_id, locale,
            place_id=payload.place_id, category=payload.category, query=payload.query,
            force=payload.force,
        )  # fmt: skip


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


@router.get("/trips/{trip_id}/proposals")
async def trip_proposals(trip_id: UUID, request: Request):
    """Change proposals of the weather re-check (Ш-40), newest first. A pending proposal made
    for an older plan version is shown as `expired`. Docs: docs/reviews/Ш-40.md."""
    access = bearer_token(request)
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        trip = await store.get_trip_row(conn, user["id"], trip_id)
        if trip is None:
            raise AppError(404, "not_found")
        return await live_proposals.list_json(conn, trip, locale)


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(proposal_id: UUID, request: Request):
    """Apply a proposal (409 `proposal_decided`, `proposal_stale`, `proposal_not_applicable`)."""
    access = bearer_token(request)
    locale = _locale(request)
    db = request.app.state.db
    provider = getattr(request.app.state, "weather_provider", None)
    forecast = None
    if provider is not None:  # outside the transaction: the provider has its own
        today = clock.local_today()
        forecast = await city_forecast(provider, [today + timedelta(days=i) for i in range(16)])
    async with db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        result = await live_proposals.accept(
            conn, _router(request), user["id"], proposal_id, locale, forecast
        )
    if result is None:  # the expiry was committed above; now tell the client
        raise AppError(409, "proposal_stale")
    return result


@router.post("/proposals/{proposal_id}/decline")
async def decline_proposal(proposal_id: UUID, request: Request):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await live_proposals.decline(conn, user["id"], proposal_id)
