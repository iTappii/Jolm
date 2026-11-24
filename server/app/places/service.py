"""Pure logic for places: localization fallback, open-now, bbox/query validation."""

from datetime import datetime, time, tzinfo
from typing import Dict, Iterable, List, Optional, Tuple

from app.regions import all_regions, default_region

# Max bbox span in degrees (protects the server: one region fits easily).
MAX_BBOX_SPAN_DEG = 2.0

_ROUND_CLOCK_CLOSE = time(23, 59)


def pick_text(
    row: dict, base: str, locale: str, chain: Optional[Iterable[str]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """First non-empty `<base>_<lang>` along the fallback chain; returns (text, lang).

    ru -> ru, en, kk ; en -> en, ru, kk (no transliteration available, so a Cyrillic name
    is still better than nothing).
    """
    if chain is None:
        chain = ("ru", "en", "kk") if locale == "ru" else ("en", "ru", "kk")
    for lang in chain:
        value = row.get("%s_%s" % (base, lang))
        if value and value.strip():
            return value, lang
    return None, None


def parse_bbox(raw: str) -> Tuple[float, float, float, float]:
    """'west,south,east,north' -> floats. Raises ValueError with a short reason."""
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("bbox needs 4 numbers")
    try:
        west, south, east, north = (float(p) for p in parts)
    except ValueError:
        raise ValueError("bbox values must be numbers") from None
    for v in (west, south, east, north):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("bbox values must be finite")
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("longitude out of range")
    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("latitude out of range")
    if west >= east or south >= north:
        raise ValueError("bbox must satisfy west < east and south < north")
    if east - west > MAX_BBOX_SPAN_DEG or north - south > MAX_BBOX_SPAN_DEG:
        raise ValueError("bbox too large")
    return west, south, east, north


def like_pattern(q: str) -> str:
    """Escape LIKE wildcards (backslash is the default ILIKE escape) and wrap in %...%."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + escaped + "%"


def _covers(opens: time, closes: time, t: time) -> bool:
    """Same-day part of an interval that starts today."""
    if opens == time(0, 0) and closes == _ROUND_CLOCK_CLOSE:
        return True
    if closes > opens:
        return opens <= t < closes
    return t >= opens  # runs past midnight: today's part is [opens, 24:00)


def region_tz(lat: float, lon: float) -> tzinfo:
    """Time zone of the region covering the point (smallest box wins), else the default region."""
    inside = [r for r in all_regions() if r.contains(lat, lon)]
    if inside:
        return min(inside, key=lambda r: (r.bbox[2] - r.bbox[0]) * (r.bbox[3] - r.bbox[1])).tz
    return default_region().tz


def is_open_now(
    hours: List[Tuple[int, time, time]],
    now: Optional[datetime] = None,
    tz: Optional[tzinfo] = None,
) -> Optional[bool]:
    """Is the place open at `now` (default: current time in the region time zone)?

    `hours` = (weekday 0=Mon, opens, closes). closes <= opens -> past midnight (spills into
    the next weekday); 00:00-23:59 -> round the clock. None when there are no hours at all.
    """
    if not hours:
        return None
    tz = tz or default_region().tz
    if now is None:
        now = datetime.now(tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    today = now.weekday()
    yesterday = (today - 1) % 7
    t = now.time().replace(second=0, microsecond=0, tzinfo=None)
    for weekday, opens, closes in hours:
        if weekday == today and _covers(opens, closes, t):
            return True
        # spill-over of yesterday's past-midnight interval into the early hours of today
        if (
            weekday == yesterday
            and closes <= opens
            and not (opens == time(0, 0) and closes == _ROUND_CLOCK_CLOSE)
        ):
            if t < closes:
                return True
    return False


def group_hours(hours: List[Tuple[int, time, time]]) -> List[Dict]:
    days: Dict[int, List[Dict[str, str]]] = {}
    for weekday, opens, closes in hours:
        days.setdefault(weekday, []).append(
            {"opens": opens.strftime("%H:%M"), "closes": closes.strftime("%H:%M")}
        )
    return [{"weekday": d, "intervals": days[d]} for d in sorted(days)]


def today_block(
    hours: List[Tuple[int, time, time]], now: datetime, tz: Optional[tzinfo] = None
) -> Optional[Dict]:
    """Today's opening hours for the card (Ш-70), by the calendar day in the region time zone.

    None when no hours are known. `opens` = first interval's start, `closes` = last interval's end
    (a lunch break is not shown; closes <= opens means past midnight, "02:00" is the next night).
    A day with no intervals: closed_today, opens/closes null (the place may still be open from
    yesterday's past-midnight interval, then open_now is true). Round the clock: open_24h with
    00:00-23:59.
    """
    if not hours:
        return None
    tz = tz or default_region().tz
    local = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    today = sorted((o, c) for d, o, c in hours if d == local.weekday())
    open_now = bool(is_open_now(hours, local, tz))
    if not today:
        return {
            "opens": None, "closes": None, "open_now": open_now,
            "open_24h": False, "closed_today": True,
        }  # fmt: skip
    round_clock = any(o == time(0, 0) and c == _ROUND_CLOCK_CLOSE for o, c in today)
    return {
        "opens": today[0][0].strftime("%H:%M"),
        "closes": today[-1][1].strftime("%H:%M"),
        "open_now": open_now,
        "open_24h": round_clock,
        "closed_today": False,
    }
