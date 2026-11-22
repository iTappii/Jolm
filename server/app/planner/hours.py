"""Opening hours and visit lengths for the day layout (Ш-34). Pure, minutes since midnight.

Hours rows are `(weekday 0=Mon, opens, closes)` as in `place_hours` (see places.service
.is_open_now): closes <= opens runs past midnight, 00:00-23:59 is round the clock. All times are
region wall-clock; the layout never converts, it works on local dates.
"""

from datetime import date, time
from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID

from app.db import fetch_all
from app.planner import sql
from app.planner.model import Place

HoursRows = Sequence[Tuple[int, time, time]]
Window = Tuple[int, int]  # [open, close) in minutes since midnight of the local date

ROUND_CLOCK_CLOSE = time(23, 59)
# No hours in the database: assume a plain daytime opening and say so in the plan.
# OPEN: not an SSOT question; data quality. The stop carries `hours_assumed=True`.
ASSUMED_WINDOW: Window = (9 * 60, 21 * 60)

# Typical visit length, minutes, when `typical_visit_min` is NULL: category, then group, then 60.
DEFAULT_VISIT_MIN: Dict[str, int] = {
    "landmark": 30, "monument": 20, "historic": 45, "religious": 30,
    "museum": 90, "gallery": 60, "theatre": 120, "entertainment": 90, "amusement": 120,
    "spa": 120, "park": 60, "garden": 60, "mountain": 180, "viewpoint": 30, "lake": 90,
    "ski": 240, "market": 60, "mall": 60, "coffee": 30, "bakery": 30, "bar": 90,
    "nightclub": 120,
    "sights": 45, "culture": 75, "nature": 90, "shopping": 60, "food": 60,
}  # fmt: skip
FALLBACK_VISIT_MIN = 60
MOUNTAIN_VISIT_MIN = 180


def visit_minutes(place: Place) -> int:
    if place.typical_visit_min:
        return place.typical_visit_min
    if place.is_mountain:
        return MOUNTAIN_VISIT_MIN
    for slug in (place.category, place.parent):
        if slug in DEFAULT_VISIT_MIN:
            return DEFAULT_VISIT_MIN[slug]
    return FALLBACK_VISIT_MIN


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def windows(hours: Optional[HoursRows], day: date) -> Optional[List[Window]]:
    """Open intervals on `day`, merged and sorted. None = hours unknown, [] = closed all day.

    Includes the early-morning spill-over of yesterday's past-midnight interval; today's own
    past-midnight interval is cut at 24:00 (the layout never plans past midnight).
    """
    if not hours:
        return None
    today = day.weekday()
    yesterday = (today - 1) % 7
    out: List[Window] = []
    for weekday, opens, closes in hours:
        o, c = _minutes(opens), _minutes(closes)
        round_clock = opens == time(0, 0) and closes == ROUND_CLOCK_CLOSE
        if weekday == today:
            out.append((0, 1440) if round_clock else ((o, c) if c > o else (o, 1440)))
        elif weekday == yesterday and c <= o and not round_clock and c > 0:
            out.append((0, c))
    out.sort()
    merged: List[Window] = []
    for a, b in out:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def earliest_start(wins: Sequence[Window], not_before: int, visit: int) -> Optional[int]:
    """Earliest start >= not_before such that [start, start + visit) lies in one window."""
    for a, b in wins:
        start = max(not_before, a)
        if start + visit <= b:
            return start
    return None


async def load_hours(
    conn, place_ids: Sequence[UUID]
) -> Mapping[UUID, List[Tuple[int, time, time]]]:
    out: Dict[UUID, List[Tuple[int, time, time]]] = {}
    if not place_ids:
        return out
    for row in await fetch_all(conn, sql.HOURS, {"ids": list(place_ids)}):
        out.setdefault(row["place_id"], []).append((row["weekday"], row["opens"], row["closes"]))
    return out
