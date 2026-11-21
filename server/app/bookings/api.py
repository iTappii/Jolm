"""Bookings skeleton (Ш-49, SSOT §9; OPEN(SSOT §16.7)). Prefix /v1, bearer auth, no-store.

    POST /bookings   body: {"place_id", "kind": "table"|"room"|"ticket"|"food", "party_size": 1,
                     "starts_at": ISO with offset, "ends_at": ISO (room), "event_id", "note"}
                     header `Idempotency-Key` (optional): a repeat returns the first booking
                     -> 201 booking | 200 (replay)
    GET  /bookings?limit&cursor -> {"items": [booking], "next_cursor"}   newest first
    GET  /bookings/{id}         -> booking (a `pending` one is refreshed from the partner)

    booking: {"id", "place": {"id", "name"}, "kind", "status", "party_size", "starts_at",
              "ends_at", "event_id", "note", "created_at", "updated_at"}
    status: pending | confirmed | declined | cancelled | failed

Errors: 404 unknown place; 422 `booking_not_supported` (no partner for that kind) or invalid body
(`starts_at` in the past, per-kind fields); 409 `booking_unavailable` (the partner cannot take
it); 429 `rate_limited` (20 per person per 24 hours). No payment in the app (ADR 0003 п.7).
The place card tells which places take bookings: `booking: {"available": true, "kinds": [...]}`,
null for a place with no partner.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response

from app.auth import sessions
from app.auth.api import bearer_token
from app.bookings import service
from app.i18n import pick_locale
from app.live import clock

router = APIRouter(prefix="/v1", tags=["bookings"])

MAX_KEY_CHARS = 100


@router.post("/bookings", status_code=201)
async def create_booking(
    payload: service.BookingCreate,
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(None, max_length=MAX_KEY_CHARS),
):
    access = bearer_token(request)
    locale = pick_locale(request.headers.get("accept-language"))
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        booking, created = await service.create(
            conn, user["id"], payload, idempotency_key, clock.now(), locale
        )
    if not created:
        response.status_code = 200
    return booking


@router.get("/bookings")
async def list_bookings(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, max_length=200),
):
    access = bearer_token(request)
    locale = pick_locale(request.headers.get("accept-language"))
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await service.list_mine(conn, user["id"], locale, limit, cursor)


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: UUID, request: Request, response: Response):
    access = bearer_token(request)
    locale = pick_locale(request.headers.get("accept-language"))
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await service.get_one(conn, user["id"], booking_id, locale)
