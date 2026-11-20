"""Pure logic for places: localization fallback, open-now, bbox/query validation."""

from datetime import datetime, time
from typing import Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

ALMATY_TZ = ZoneInfo("Asia/Almaty")

# Max bbox span in degrees (protects the server: Almaty region fits easily).
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


def is_open_now(
    hours: List[Tuple[int, time, time]], now: Optional[datetime] = None
) -> Optional[bool]:
    """Is the place open at `now` (default: current time in Asia/Almaty)?

    `hours` = (weekday 0=Mon, opens, closes). closes <= opens -> past midnight (spills into
    the next weekday); 00:00-23:59 -> round the clock. None when there are no hours at all.
    """
    if not hours:
        return None
    if now is None:
        now = datetime.now(ALMATY_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=ALMATY_TZ)
    else:
        now = now.astimezone(ALMATY_TZ)
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
