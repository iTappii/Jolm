"""Trip event suggestions and the corresponding venue scoring signal (Ш-48, SSOT §5.1).

Events are offered with their published time. A venue with an eligible event gains a ranking
bonus. The day layout still schedules place visits separately from these optional suggestions.
"""

from datetime import date
from typing import Any, Dict, List, Mapping, Optional

from app.events import service
from app.planner.area import ALMATY_BBOX
from app.planner.layout import DAY_END, DAY_START
from app.planner.model import Place
from app.planner.scoring import DEFAULT_PACE


class EventIndex:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.items = rows
        self._at_place = {row["place_id"] for row in rows if row["place_id"]}

    def bonus(self, place: Place, start: date, end: date) -> float:
        return 1.0 if place.id in self._at_place else 0.0


async def load_event_index(conn, brief: Mapping[str, Any]) -> EventIndex:
    rows = await trip_events(conn, brief["start_date"], brief["end_date"], brief.get("pace"))
    return EventIndex(rows)


async def trip_events(
    conn, start: date, end: date, pace: Optional[str], limit: int = service.DEFAULT_LIMIT
) -> List[Dict[str, Any]]:
    pace = pace if pace in DAY_START else DEFAULT_PACE
    return await service.load_events(
        conn, start, end, ALMATY_BBOX, limit, active_minutes=(DAY_START[pace], DAY_END[pace])
    )
