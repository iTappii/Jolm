"""Partner adapters (Ш-49, SSOT §9; OPEN(SSOT §16.7): partners, API shapes and payment are not
decided). One adapter per partner integration; the booking service only talks to this interface.

A real adapter calls the partner's API. That call must not run inside the API request once a
partner is slow or flaky: move `create_booking` to a job then (the stub is instant, so the
skeleton calls it inline). Money never goes through Jol (ADR 0003 п.7): a booking is a request.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from app.regions import default_region


@dataclass(frozen=True)
class BookingRequest:
    booking_id: UUID  # ours; the partner can use it as an idempotency reference
    kind: str  # table | room | ticket | food
    place_ref: Optional[str]  # the partner's id of the place (`partner_places.external_ref`)
    party_size: int
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    event_id: Optional[UUID]
    note: Optional[str]


@dataclass(frozen=True)
class Availability:
    available: bool
    reason: Optional[str] = None  # machine-readable, e.g. "party_too_large"


@dataclass(frozen=True)
class PartnerResult:
    status: str  # pending | confirmed | declined | failed
    external_ref: Optional[str] = None


@dataclass(frozen=True)
class BookingLimits:
    """What a partner accepts for one booking kind; shown on the place card and enforced by
    `POST /v1/bookings` before the partner is asked. Times are the partner's local time."""

    party_min: int = 1
    party_max: int = 10
    min_lead_minutes: int = 0  # `starts_at` at least this far from now
    max_advance_days: Optional[int] = None  # ... and at most this many days ahead
    hours_open: Optional[str] = None  # "HH:MM"; `starts_at` local time within [open, close]
    hours_close: Optional[str] = None
    max_nights: Optional[int] = None  # room: longest stay
    timezone: str = field(default_factory=lambda: default_region().timezone)

    def to_json(self) -> Dict[str, Any]:
        return {
            "party_min": self.party_min,
            "party_max": self.party_max,
            "min_lead_minutes": self.min_lead_minutes,
            "max_advance_days": self.max_advance_days,
            "hours": (
                {"open": self.hours_open, "close": self.hours_close} if self.hours_open else None
            ),
            "max_nights": self.max_nights,
            "timezone": self.timezone,
        }


class PartnerAdapter(Protocol):
    def limits(self, kind: str) -> Optional[BookingLimits]: ...

    async def availability(self, request: BookingRequest) -> Availability: ...

    async def create_booking(self, request: BookingRequest) -> PartnerResult: ...

    async def status(self, external_ref: str) -> str: ...

    # Optional (Ш-55): ask the partner to cancel; returns the booking's status afterwards
    # ("cancelled" when it worked). An adapter without it is cancelled on our side only.
    # async def cancel(self, external_ref: str) -> str: ...


STUB_MAX_PARTY = 10
STUB_LIMITS = {
    "table": BookingLimits(
        party_max=STUB_MAX_PARTY,
        min_lead_minutes=30,
        max_advance_days=60,
        hours_open="10:00",
        hours_close="23:00",
    ),
    "room": BookingLimits(
        party_max=STUB_MAX_PARTY, min_lead_minutes=60, max_advance_days=365, max_nights=30
    ),
    "ticket": BookingLimits(party_max=STUB_MAX_PARTY, max_advance_days=180),
    "food": BookingLimits(party_max=STUB_MAX_PARTY),
}


class StubAdapter:
    """Deterministic stand-in: a party up to STUB_MAX_PARTY is available and confirmed at once;
    `STUB_LIMITS` are its booking limits."""

    def limits(self, kind: str) -> Optional[BookingLimits]:
        return STUB_LIMITS.get(kind)

    async def availability(self, request: BookingRequest) -> Availability:
        if request.party_size > STUB_MAX_PARTY:
            return Availability(False, "party_too_large")
        return Availability(True)

    async def create_booking(self, request: BookingRequest) -> PartnerResult:
        return PartnerResult("confirmed", "stub-%s" % request.booking_id)

    async def status(self, external_ref: str) -> str:
        return "confirmed"

    async def cancel(self, external_ref: str) -> str:
        return "cancelled"


_ADAPTERS: Dict[str, PartnerAdapter] = {"stub": StubAdapter()}


def supported_names() -> List[str]:
    return list(_ADAPTERS)


def limits_of(adapter: Any, kind: str) -> Optional[BookingLimits]:
    """The adapter's limits for `kind`; None when it declares none (nothing is enforced)."""
    declared = getattr(adapter, "limits", None)
    return declared(kind) if callable(declared) else None


def get_adapter(name: str) -> Optional[PartnerAdapter]:
    return _ADAPTERS.get(name)
