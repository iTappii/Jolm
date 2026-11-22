"""Events for tourists (Ш-48, SSOT §5.1, §12). Raw, parameterized SQL; shared by the public API,
the planner, the trip read model and the chat tool.

Dates are calendar dates of the region; times in answers are ISO strings in its time zone.
Ads (SSOT §12; OPEN(SSOT §16.9): the label text is a working default, "Реклама" / "Ad"):
an event is shown as an ad only when `events.is_promoted` AND its place is not public
(attractions and state places never carry ads, whatever the table says).
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.db import fetch_all
from app.places import service as places
from app.regions import default_region

MAX_SPAN_DAYS = 62
DEFAULT_SPAN_DAYS = 14
DEFAULT_LIMIT = 200
MAX_LIMIT = 500
AD_LABEL = {"ru": "Реклама", "en": "Ad"}  # OPEN(SSOT §16.9)

EVENTS = """
WITH windows AS (
    SELECT (day + %(opens)s::interval) AT TIME ZONE %(tz)s AS opens,
           (day + %(closes)s::interval) AT TIME ZONE %(tz)s AS closes
    FROM generate_series(%(start)s::date::timestamp, %(end)s::date::timestamp,
                         interval '1 day') AS d(day)
)
SELECT e.id, e.title_ru, e.title_en, e.description_ru, e.description_en,
       e.starts_at, e.ends_at, e.price_kzt, e.sponsor,
       (e.is_promoted AND NOT coalesce(p.is_public, false)) AS is_ad,
       c.slug AS category,
       p.id AS place_id, p.name_ru AS place_name_ru, p.name_en AS place_name_en,
       ST_Y(coalesce(e.geom, p.geom)::geometry) AS lat,
       ST_X(coalesce(e.geom, p.geom)::geometry) AS lon
FROM events e
LEFT JOIN places p ON p.id = e.place_id
LEFT JOIN place_categories c ON c.id = e.category_id
WHERE e.starts_at < ((%(end)s::date + 1)::timestamp AT TIME ZONE %(tz)s)
  AND coalesce(e.ends_at, e.starts_at) >= (%(start)s::date::timestamp AT TIME ZONE %(tz)s)
  AND EXISTS (SELECT FROM windows w WHERE e.starts_at < w.closes
              AND (e.starts_at >= w.opens OR e.ends_at > w.opens))
  AND (p.id IS NULL OR p.status = 'active')
  AND coalesce(e.geom, p.geom) IS NOT NULL
  AND (%(place_id)s::uuid IS NULL OR e.place_id = %(place_id)s::uuid)
  AND (%(bbox)s::boolean IS FALSE
       OR ST_Intersects(coalesce(e.geom, p.geom)::geometry,
                        ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)))
ORDER BY e.starts_at, e.id
LIMIT %(limit)s
"""


def window_end(start: date, end: Optional[date]) -> date:
    if end is None:
        return start + timedelta(days=min(DEFAULT_SPAN_DAYS, (date.max - start).days))
    if end < start:
        raise ValueError("to is before from")
    if (end - start).days > MAX_SPAN_DAYS:
        raise ValueError(f"the window is longer than {MAX_SPAN_DAYS} days")
    return end


async def load_events(
    conn,
    start: date,
    end: date,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    limit: int = DEFAULT_LIMIT,
    place_id: Optional[UUID] = None,
    active_minutes: Tuple[int, int] = (0, 24 * 60),
) -> List[Dict[str, Any]]:
    """Return events overlapping daily local hours; an event without an end occurs at its start."""
    west, south, east, north = bbox or (None, None, None, None)
    return await fetch_all(
        conn,
        EVENTS,
        {
            "start": start, "end": end, "opens": timedelta(minutes=active_minutes[0]),
            "closes": timedelta(minutes=active_minutes[1]), "bbox": bbox is not None, "west": west,
            "south": south, "east": east, "north": north, "limit": limit, "place_id": place_id,
            "tz": default_region().timezone,
        },
    )  # fmt: skip


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(default_region().tz).isoformat() if value else None


def event_json(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    """Public shape (API, card, trip, planner summary for the model).

    `is_ad` / `ad_label`: promoted event ("Реклама" / "Ad"); the app must show the label.
    """
    title, lang = places.pick_text(row, "title", locale)
    description, _ = places.pick_text(row, "description", locale)
    place = None
    if row["place_id"]:
        name, _ = places.pick_text(row, "place_name", locale)
        place = {"id": str(row["place_id"]), "name": name or ""}
    return {
        "id": str(row["id"]),
        "title": title or "",
        "title_lang": lang,
        "description": description,
        "starts_at": _iso(row["starts_at"]),
        "ends_at": _iso(row["ends_at"]),
        "price_kzt": row["price_kzt"],
        "organizer": row["sponsor"],
        "category": row["category"],
        "lat": row["lat"],
        "lon": row["lon"],
        "place": place,
        "is_ad": bool(row["is_ad"]),
        "ad_label": AD_LABEL.get(locale, AD_LABEL["en"]) if row["is_ad"] else None,
    }
