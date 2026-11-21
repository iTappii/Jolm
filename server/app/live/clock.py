"""The live plan's clock: one place to fake time in tests."""

from datetime import date, datetime, timezone
from typing import Callable, Optional

from app.routing.service import ALMATY_TZ

_override: Optional[Callable[[], datetime]] = None


def now() -> datetime:
    return _override() if _override else datetime.now(timezone.utc)


def set_clock(fn: Optional[Callable[[], datetime]]) -> None:
    global _override
    _override = fn


def local_today(moment: Optional[datetime] = None) -> date:
    return (moment or now()).astimezone(ALMATY_TZ).date()
