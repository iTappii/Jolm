"""Own crowd data (Ш-47, SSOT §7.3; TECH_PLAN §2 п.5). Raw, parameterized SQL.

Flow: a signed-in person who is physically at a place sends "I am here" (`checkin`) or a crowd
report (`empty` / `normal` / `busy`). Both carry the person's location, which is checked
against the place (CHECKIN_RADIUS_M) and then dropped: only the distance is stored. The
`crowd.aggregate` job (hourly) turns the reports of the last WINDOW_DAYS into
`place_crowd_profile` (local weekday x hour, exponentially decayed average). The card and the
planner read the profile and use it only when there is enough data (thresholds below).
"""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.db import execute, fetch_all, fetch_one
from app.errors import AppError
from app.regions import default_region

CHECKIN_RADIUS_M = 200  # places are points; a park or a mall is large, a phone is not exact
CHECKIN_REPEAT = timedelta(minutes=30)  # the same person at the same place: one check-in
CROWD_REPEAT = timedelta(hours=2)  # ... one crowd report; a repeat is answered, not stored
DAILY_LIMIT = 40  # per person and 24 hours, check-ins and reports together
LEVELS = {"empty": 0, "normal": 1, "busy": 2}

# OPEN(SSOT §16.5): use our voluntary on-site reports until the source is decided.
WINDOW_DAYS = 60  # older reports are not used and are deleted by the job
HALF_LIFE_DAYS = 14.0  # a report counts half after two weeks
# Thresholds for showing / using the data (no data -> nothing is shown and nothing is penalised).
MIN_PLACE_SAMPLES = 5  # reports in the profile of a place before the card shows a crowd block
MIN_CELL_SAMPLES = 2  # reports in a weekday x hour cell before "right now" is shown
PLANNER_HOURS = (9, 21)  # the planner averages the daytime cells [9, 21)
EMPTY_BELOW = 1 / 3  # label thresholds for a 0..1 level
BUSY_FROM = 2 / 3

PLACE_FOR_CHECK = """
SELECT p.id,
       ST_Distance(p.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography) AS dist
FROM places p WHERE p.id = %(place)s AND p.status = 'active'
FOR KEY SHARE
"""
LOCK_USER = "SELECT id FROM users WHERE id = %s FOR UPDATE"
RECENT_COUNT = (
    "SELECT count(*) AS n, min(created_at) AS oldest FROM place_crowd_reports"
    " WHERE user_id = %s AND created_at > %s - interval '24 hours'"
)
LAST_SAME = (
    "SELECT 1 AS ok FROM place_crowd_reports WHERE user_id = %s AND place_id = %s AND kind = %s"
    " AND created_at > %s - %s::interval"
)
INSERT = """
INSERT INTO place_crowd_reports (place_id, user_id, kind, level, distance_m, created_at)
VALUES (%s, %s, %s, %s, %s, %s)
"""

# Rebuild: decayed average per place x local weekday x hour. `now` is a parameter, so tests and
# the job agree on one instant. isodow 1 = Monday.
AGGREGATE = """
INSERT INTO place_crowd_profile (place_id, weekday, hour, level, samples, updated_at)
SELECT r.place_id,
       (extract(isodow FROM r.created_at AT TIME ZONE %(tz)s)::int - 1)::smallint,
       extract(hour FROM r.created_at AT TIME ZONE %(tz)s)::smallint,
       sum(CASE r.level WHEN 0 THEN 0.0 WHEN 1 THEN 0.5 ELSE 1.0 END
           * power(0.5, extract(epoch FROM (%(now)s - r.created_at)) / 86400.0 / %(half)s))
         / sum(power(0.5, extract(epoch FROM (%(now)s - r.created_at)) / 86400.0 / %(half)s)),
       count(*)::int,
       %(now)s
FROM place_crowd_reports r
WHERE r.kind = 'crowd' AND r.created_at > %(now)s - make_interval(days => %(window)s)
  AND r.created_at <= %(now)s
GROUP BY 1, 2, 3
"""
PROFILE_BY_PLACE = (
    "SELECT weekday, hour, level, samples, updated_at FROM place_crowd_profile"
    " WHERE place_id = %s ORDER BY weekday, hour"
)
# Places with enough data, and the sample-weighted mean of their daytime cells.
PLANNER_LEVELS = """
SELECT place_id,
       sum(level * samples) / sum(samples) AS level
FROM place_crowd_profile
WHERE hour >= %(from)s AND hour < %(to)s
GROUP BY place_id
HAVING sum(samples) >= %(min)s
"""


def label(level: float) -> str:
    if level < EMPTY_BELOW:
        return "empty"
    return "busy" if level >= BUSY_FROM else "normal"


async def _distance(conn, place_id: UUID, lat: float, lon: float) -> int:
    row = await fetch_one(conn, PLACE_FOR_CHECK, {"lat": lat, "lon": lon, "place": place_id})
    if row is None:
        raise AppError(404, "not_found")
    distance = int(math.ceil(row["dist"]))
    if distance > CHECKIN_RADIUS_M:
        raise AppError(422, "too_far_from_place")
    return distance


async def record(
    conn,
    user_id: UUID,
    place_id: UUID,
    kind: str,
    lat: float,
    lon: float,
    level: Optional[str],
    now: datetime,
) -> Dict[str, Any]:
    """Store a check-in or a report. `{"recorded": False}` for a repeat inside the window."""
    # Hold the per-person lock across both quota checks and the insert.
    if not await fetch_one(conn, LOCK_USER, (user_id,)):
        raise AppError(401, "unauthorized")
    distance = await _distance(conn, place_id, lat, lon)
    window = CHECKIN_REPEAT if kind == "checkin" else CROWD_REPEAT
    if await fetch_one(conn, LAST_SAME, (user_id, place_id, kind, now, window)):
        return {"recorded": False, "distance_m": distance}
    recent = await fetch_one(conn, RECENT_COUNT, (user_id, now))
    if recent["n"] >= DAILY_LIMIT:
        remaining = recent["oldest"] + timedelta(days=1) - now
        raise AppError(
            429, "rate_limited", headers={"Retry-After": str(math.ceil(remaining.total_seconds()))}
        )
    await execute(
        conn,
        INSERT,
        (place_id, user_id, kind, LEVELS[level] if level else None, distance, now),
    )
    return {"recorded": True, "distance_m": distance}


async def aggregate(conn, now: datetime) -> int:
    """Rebuild the profile from the reports of the last WINDOW_DAYS; drop older reports.

    Check-ins are not touched (the visit metric of Ш-50 reads them). Returns the cell count.
    """
    await execute(
        conn,
        "DELETE FROM place_crowd_reports WHERE kind = 'crowd'"
        " AND created_at <= %s - make_interval(days => %s)",
        (now, WINDOW_DAYS),
    )
    await execute(conn, "DELETE FROM place_crowd_profile")
    return await execute(
        conn,
        AGGREGATE,
        {
            "now": now,
            "half": HALF_LIFE_DAYS,
            "window": WINDOW_DAYS,
            "tz": default_region().timezone,
        },
    )


# --- reading: the card and the planner -------------------------------------------------------


def card_block(rows: List[Dict[str, Any]], now: datetime) -> Optional[Dict[str, Any]]:
    """The `crowd` block of the place card, or None when the place has too little data.

    {"now": {"level", "label", "samples"} | null, "today": [{"hour", "level", "label", "samples"}],
     "samples": <reports in the profile>, "updated_at": ISO}. `level` is 0 (empty) .. 1 (packed).
    """
    total = sum(r["samples"] for r in rows)
    if total < MIN_PLACE_SAMPLES:
        return None
    local = now.astimezone(default_region().tz)
    today = [
        r for r in rows if r["weekday"] == local.weekday() and r["samples"] >= MIN_CELL_SAMPLES
    ]
    cells = [
        {
            "hour": r["hour"],
            "level": round(r["level"], 2),
            "label": label(r["level"]),
            "samples": r["samples"],
        }
        for r in today
    ]
    current = next((c for c in cells if c["hour"] == local.hour), None)
    return {
        "now": (
            {k: current[k] for k in ("level", "label", "samples")} if current is not None else None
        ),
        "today": cells,
        "samples": total,
        "updated_at": max(r["updated_at"] for r in rows).isoformat(),
    }


async def place_block(conn, place_id: UUID, now: datetime) -> Optional[Dict[str, Any]]:
    return card_block(await fetch_all(conn, PROFILE_BY_PLACE, (place_id,)), now)


class ProfileCrowd:
    """Planner crowd source backed by the profile (`signals.CrowdSource`): the mean daytime
    level of a place, or None (unknown, costs nothing in the score) below MIN_PLACE_SAMPLES."""

    def __init__(self, levels: Dict[UUID, float]) -> None:
        self._levels = levels

    @classmethod
    async def load(cls, conn) -> "ProfileCrowd":
        rows = await fetch_all(
            conn,
            PLANNER_LEVELS,
            {"from": PLANNER_HOURS[0], "to": PLANNER_HOURS[1], "min": MIN_PLACE_SAMPLES},
        )
        return cls({r["place_id"]: float(r["level"]) for r in rows})

    def level(self, place_id: UUID) -> Optional[float]:
        return self._levels.get(place_id)
