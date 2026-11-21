"""Bookings (Ш-49, SSOT §9). Raw, parameterized SQL. See `adapters.py` for the partner side."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.bookings import adapters
from app.db import execute, fetch_all, fetch_one
from app.errors import AppError
from app.places import service as places
from app.submissions.service import decode_cursor, encode_cursor

log = logging.getLogger("app.bookings")

KINDS = ("table", "room", "ticket", "food")
DAILY_LIMIT = 20  # new bookings per person and 24 hours
MAX_NOTE = 300
MAX_PARTY = 20


class BookingCreate(BaseModel):
    """`POST /v1/bookings` body. Needed per kind: table: starts_at; room: starts_at (check-in)
    and ends_at (check-out, later); ticket: starts_at or event_id; food: nothing."""

    model_config = ConfigDict(extra="forbid")
    place_id: UUID
    kind: Literal["table", "room", "ticket", "food"]
    party_size: int = Field(1, ge=1, le=MAX_PARTY)
    starts_at: Optional[AwareDatetime] = None
    ends_at: Optional[AwareDatetime] = None
    event_id: Optional[UUID] = None
    note: Optional[str] = Field(None, max_length=MAX_NOTE)

    @model_validator(mode="after")
    def _per_kind(self) -> "BookingCreate":
        if self.kind in ("table", "room") and self.starts_at is None:
            raise ValueError("starts_at is required for %s" % self.kind)
        if self.kind == "room" and (self.ends_at is None or self.ends_at <= self.starts_at):
            raise ValueError("ends_at must be after starts_at for a room")
        if self.kind == "ticket" and self.starts_at is None and self.event_id is None:
            raise ValueError("a ticket needs starts_at or event_id")
        if self.event_id is not None and self.kind != "ticket":
            raise ValueError("event_id is only for a ticket")
        if self.kind != "room" and self.ends_at is not None:
            raise ValueError("ends_at is only for a room")
        return self


LOCK_USER = "SELECT id FROM users WHERE id = %s FOR UPDATE"
PLACE_ACTIVE = "SELECT id FROM places WHERE id = %s AND status = 'active'"
CURRENT_EVENT = (
    "SELECT id FROM events WHERE id = %s AND place_id = %s AND coalesce(ends_at, starts_at) >= %s"
)
BY_KEY = (
    "SELECT b.*, p.name_ru, p.name_en, p.name_kk FROM bookings b"
    " JOIN places p ON p.id = b.place_id WHERE b.user_id = %s AND b.idempotency_key = %s"
)
RECENT = (
    "SELECT count(*) AS n, ceil(extract(epoch FROM min(created_at) + interval '24 hours'"
    " - clock_timestamp()))::int AS retry_after FROM bookings WHERE user_id = %s"
    " AND created_at > clock_timestamp() - interval '24 hours'"
)
PARTNER_FOR = """
SELECT pr.id AS partner_id, pr.adapter, pp.external_ref
FROM partner_places pp
JOIN partners pr ON pr.id = pp.partner_id AND pr.is_active
WHERE pp.place_id = %s AND %s = ANY(pp.kinds) AND pr.adapter = ANY(%s)
ORDER BY pr.created_at, pr.id
LIMIT 1
"""
INSERT = """
INSERT INTO bookings (id, user_id, place_id, partner_id, kind, status, payload, external_ref,
                      idempotency_key)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
GET_ONE = """
SELECT b.*, p.name_ru, p.name_en, p.name_kk, pr.adapter
FROM bookings b JOIN places p ON p.id = b.place_id JOIN partners pr ON pr.id = b.partner_id
WHERE b.id = %s AND b.user_id = %s
"""
LIST = """
SELECT b.*, p.name_ru, p.name_en, p.name_kk
FROM bookings b JOIN places p ON p.id = b.place_id
WHERE b.user_id = %(user)s
  AND (%(ts)s::timestamptz IS NULL OR (b.created_at, b.id) < (%(ts)s, %(id)s))
ORDER BY b.created_at DESC, b.id DESC
LIMIT %(limit)s
"""
KINDS_FOR_PLACE = """
SELECT k AS kind, pr.adapter
FROM partner_places pp
JOIN partners pr ON pr.id = pp.partner_id AND pr.is_active
CROSS JOIN LATERAL unnest(pp.kinds) AS k
WHERE pp.place_id = %s AND pr.adapter = ANY(%s)
ORDER BY pr.created_at, pr.id
"""


async def card_block(conn, place_id: UUID) -> Optional[Dict[str, Any]]:
    """`booking` of the place card: None for a place with no partner. `limits` maps each offered
    kind to the limits of the partner that would take it (the same one `create` picks); a kind
    whose adapter declares none maps to null."""
    rows = await fetch_all(conn, KINDS_FOR_PLACE, (place_id, adapters.supported_names()))
    first: Dict[str, str] = {}
    for row in rows:
        first.setdefault(row["kind"], row["adapter"])
    kinds = [kind for kind in KINDS if kind in first]
    if not kinds:
        return None
    limits = {}
    for kind in kinds:
        declared = adapters.limits_of(adapters.get_adapter(first[kind]), kind)
        limits[kind] = declared.to_json() if declared else None
    return {"available": True, "kinds": kinds, "limits": limits}


def check_limits(
    limits: Optional[adapters.BookingLimits], body: BookingCreate, now: datetime
) -> None:
    """422 with a machine-readable code when the request is outside the partner's limits:
    `party_too_small`, `party_too_large`, `booking_too_soon`, `booking_too_far`,
    `booking_outside_hours`, `stay_too_long`."""
    if limits is None:
        return
    if body.party_size < limits.party_min:
        raise AppError(422, "party_too_small")
    if body.party_size > limits.party_max:
        raise AppError(422, "party_too_large")
    if body.starts_at is not None:
        if body.starts_at < now + timedelta(minutes=limits.min_lead_minutes):
            raise AppError(422, "booking_too_soon")
        if limits.max_advance_days is not None and body.starts_at > now + timedelta(
            days=limits.max_advance_days
        ):
            raise AppError(422, "booking_too_far")
        if limits.hours_open and limits.hours_close and body.kind != "room":
            local = body.starts_at.astimezone(ZoneInfo(limits.timezone)).strftime("%H:%M")
            if not limits.hours_open <= local <= limits.hours_close:
                raise AppError(422, "booking_outside_hours")
    if body.kind == "room" and limits.max_nights is not None and body.ends_at is not None:
        if (body.ends_at - body.starts_at) > timedelta(days=limits.max_nights):
            raise AppError(422, "stay_too_long")


def booking_json(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    name, _ = places.pick_text(row, "name", locale)
    payload = row["payload"]
    return {
        "id": str(row["id"]),
        "place": {"id": str(row["place_id"]), "name": name or ""},
        "kind": row["kind"],
        "status": row["status"],
        "party_size": payload.get("party_size"),
        "starts_at": payload.get("starts_at"),
        "ends_at": payload.get("ends_at"),
        "event_id": payload.get("event_id"),
        "note": payload.get("note"),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def create(
    conn, user_id: UUID, body: BookingCreate, key: Optional[str], now: datetime, locale: str
) -> Tuple[Dict[str, Any], bool]:
    """Returns (booking JSON, created). A repeated Idempotency-Key returns the first booking."""
    # Serialise the rate-limit and replay checks with other requests for this user.
    if await fetch_one(conn, LOCK_USER, (user_id,)) is None:
        raise AppError(401, "unauthorized")
    if key:
        existing = await fetch_one(conn, BY_KEY, (user_id, key))
        if existing:
            return booking_json(existing, locale), False
    if await fetch_one(conn, PLACE_ACTIVE, (body.place_id,)) is None:
        raise AppError(404, "not_found")
    if body.starts_at is not None and body.starts_at < now - timedelta(minutes=5):
        raise AppError(422, "validation_error")
    if body.event_id is not None:
        if await fetch_one(conn, CURRENT_EVENT, (body.event_id, body.place_id, now)) is None:
            raise AppError(422, "validation_error")
    recent = await fetch_one(conn, RECENT, (user_id,))
    if recent["n"] >= DAILY_LIMIT:
        raise AppError(
            429, "rate_limited", headers={"Retry-After": str(max(1, recent["retry_after"]))}
        )
    link = await fetch_one(
        conn, PARTNER_FOR, (body.place_id, body.kind, adapters.supported_names())
    )
    adapter = adapters.get_adapter(link["adapter"]) if link else None
    if link is None or adapter is None:
        raise AppError(422, "booking_not_supported")
    check_limits(adapters.limits_of(adapter, body.kind), body, now)

    booking_id = uuid4()
    request = adapters.BookingRequest(
        booking_id=booking_id, kind=body.kind, place_ref=link["external_ref"],
        party_size=body.party_size, starts_at=body.starts_at, ends_at=body.ends_at,
        event_id=body.event_id, note=body.note,
    )  # fmt: skip
    try:
        availability = await adapter.availability(request)
    except Exception as exc:
        log.exception("partner availability failed", extra={"adapter": link["adapter"]})
        raise AppError(503, "booking_partner_unavailable") from exc
    if not availability.available:
        raise AppError(409, "booking_unavailable")
    try:
        result = await adapter.create_booking(request)
    except Exception:
        log.exception("partner adapter failed", extra={"adapter": link["adapter"]})
        result = adapters.PartnerResult("failed")
    payload = body.model_dump(mode="json", exclude={"place_id", "kind"}, exclude_none=True)
    await execute(
        conn,
        INSERT,
        (booking_id, user_id, body.place_id, link["partner_id"], body.kind, result.status,
         Jsonb(payload), result.external_ref, key or None),
    )  # fmt: skip
    row = await fetch_one(conn, GET_ONE, (booking_id, user_id))
    return booking_json(row, locale), True


async def get_one(conn, user_id: UUID, booking_id: UUID, locale: str) -> Dict[str, Any]:
    """One booking; a `pending` one is refreshed from the partner first."""
    row = await fetch_one(conn, GET_ONE, (booking_id, user_id))
    if row is None:
        raise AppError(404, "not_found")
    adapter = adapters.get_adapter(row["adapter"])
    if row["status"] == "pending" and row["external_ref"] and adapter is not None:
        try:
            fresh = await adapter.status(row["external_ref"])
        except Exception:
            log.exception("partner status failed", extra={"adapter": row["adapter"]})
            fresh = row["status"]
        if fresh in ("confirmed", "declined", "cancelled", "failed"):
            await execute(
                conn,
                "UPDATE bookings SET status = %s, updated_at = clock_timestamp()"
                " WHERE id = %s AND status = 'pending'",
                (fresh, booking_id),
            )
            row = await fetch_one(conn, GET_ONE, (booking_id, user_id))
    return booking_json(row, locale)


async def list_mine(
    conn, user_id: UUID, locale: str, limit: int, cursor: Optional[str]
) -> Dict[str, Any]:
    ts, ident = decode_cursor(cursor)
    rows = await fetch_all(conn, LIST, {"user": user_id, "ts": ts, "id": ident, "limit": limit + 1})
    page: List[Dict[str, Any]] = rows[:limit]
    return {
        "items": [booking_json(r, locale) for r in page],
        "next_cursor": (
            encode_cursor(page[-1]["created_at"], page[-1]["id"]) if len(rows) > limit else None
        ),
    }
