"""Inputs to scoring that other phases will provide. Each has a default that means "no data".

- memory penalties (Ф12, SSOT §8): `{category slug: penalty 0..1}`; a removed museum raises the
  penalty of `museum`, so museums show up less often but are never excluded. Empty by default.
- crowd level (Ф15, SSOT §7.3): `CrowdSource.level(place_id)` -> 0..1 or None (unknown).
  `UnknownCrowd` always answers None, which costs nothing in the score; the real source is
  `app.crowd.service.ProfileCrowd` (Ш-47), which also answers None below its sample threshold.
- event bonus (Ф16, SSOT §5.1): `no_event_bonus` returns 0 (the default in tests and for callers
  with no database); the real hook is `app.planner.events.EventIndex.bonus` (Ш-48). A hook takes
  a place and the trip dates and returns 0..1 (1 = something fitting happens there).
"""

from datetime import date
from typing import Callable, Mapping, Optional, Protocol
from uuid import UUID

MemoryPenalties = Mapping[str, float]


class CrowdSource(Protocol):
    def level(self, place_id: UUID) -> Optional[float]:
        """0 = empty ... 1 = packed; None = unknown."""


class UnknownCrowd:
    def level(self, place_id: UUID) -> Optional[float]:
        return None


# (place, trip start, trip end) -> 0..1
EventBonus = Callable[["object", date, date], float]


def no_event_bonus(place: object, start: date, end: date) -> float:
    return 0.0
