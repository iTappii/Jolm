"""Partner adapters (Ш-49, SSOT §9; OPEN(SSOT §16.7): partners, API shapes and payment are not
decided). One adapter per partner integration; the booking service only talks to this interface.

A real adapter calls the partner's API. That call must not run inside the API request once a
partner is slow or flaky: move `create_booking` to a job then (the stub is instant, so the
skeleton calls it inline). Money never goes through Jol (ADR 0003 п.7): a booking is a request.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Protocol
from uuid import UUID


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


class PartnerAdapter(Protocol):
    async def availability(self, request: BookingRequest) -> Availability: ...

    async def create_booking(self, request: BookingRequest) -> PartnerResult: ...

    async def status(self, external_ref: str) -> str: ...


STUB_MAX_PARTY = 10


class StubAdapter:
    """Deterministic stand-in: a party up to STUB_MAX_PARTY is available and confirmed at once."""

    async def availability(self, request: BookingRequest) -> Availability:
        if request.party_size > STUB_MAX_PARTY:
            return Availability(False, "party_too_large")
        return Availability(True)

    async def create_booking(self, request: BookingRequest) -> PartnerResult:
        return PartnerResult("confirmed", "stub-%s" % request.booking_id)

    async def status(self, external_ref: str) -> str:
        return "confirmed"


_ADAPTERS: Dict[str, PartnerAdapter] = {"stub": StubAdapter()}


def supported_names() -> List[str]:
    return list(_ADAPTERS)


def get_adapter(name: str) -> Optional[PartnerAdapter]:
    return _ADAPTERS.get(name)
