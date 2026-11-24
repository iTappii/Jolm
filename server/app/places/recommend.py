"""Recommendation signals for the model (Ш-68): "best place for a tourist", not a name list.

A tourist does not know the city, so the model must be able to pick 2-3 places itself. For that
every place of a search result carries compact signals (popularity, distance from the anchor,
open now and until when, price, address, category in words) and the list is sorted best-first.

The anchor (where "near" is measured from), in order: the tourist's location if the app sent it
this turn -> the accommodation from the brief -> the centre of the default region. A location is
used for this one turn only: it is never stored, never logged, and never reaches the model as
coordinates (only distances rounded to 100 m; places of such a result carry no coordinates).
Raw parameterized SQL (SSOT §14.1).
"""

import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.db import fetch_all
from app.places import service
from app.regions import Region, default_region

# ---------------------------------------------------------------- the ranking, in one place
# score = TIER_STEP * dish tier bonus + W_DISTANCE * near + quality * (FLOOR + (1 - FLOOR) * near)
# quality = W_POPULARITY * pop + W_OPEN * open + W_COMPLETE * complete; every signal is in 0..1.
# A far place keeps only QUALITY_FLOOR of its fame/openness, a place closed now only CLOSED_FACTOR
# of its score. The weights add up to 1, so a better dish match (tier) always beats the signals.
W_POPULARITY = 0.30  # places.popularity / POPULARITY_REF (0 = unknown, scores 0)
W_DISTANCE = 0.40  # 1 / (1 + (distance / DISTANCE_HALF_M)^2): 1 at the anchor, 0.5 at HALF_M,
# ~0.1 at 3 x HALF_M: a famous place across the city does not beat a good one around the corner
W_OPEN = 0.20  # open now 1, no opening hours 0.5 (unknown), closed 0
W_COMPLETE = 0.10  # share of (opening hours, address) the place has: data we can vouch for
QUALITY_FLOOR = 0.4  # share of fame/openness a place keeps however far it is
CLOSED_FACTOR = 0.5  # a place closed right now is worth half (the tourist wants to go now)
POPULARITY_REF = 100  # popularity is 0..100 in the data
DISTANCE_HALF_M = 1500
OPEN_UNKNOWN = 0.5
TIER_STEP = 2.0  # > the sum of the weights: a dish tier is never overturned by the signals
DISH_TIER_BONUS = {0: 3, 1: 2, 2: 1, 3: 0}  # menu, name, cuisine, related (places/dishes.py)

CANDIDATES = 30  # the search takes this many, ranks them, the model gets the top `limit`
ANCHOR_RADIUS_M = 30_000  # candidates are looked for this far from the anchor
LOCATION_ROUND_M = 100  # a distance computed from the tourist's location is rounded to this
ADDRESS_CHARS = 60
# price level of an average check in tenge: < CHEAP -> 1, < MID -> 2, otherwise 3
PRICE_CHEAP_KZT = 3000
PRICE_MID_KZT = 7000

SOURCE_LOCATION, SOURCE_LODGING, SOURCE_REGION = "location", "lodging", "region"


@dataclass(frozen=True)
class Anchor:
    lat: float
    lon: float
    source: str

    def __repr__(self) -> str:  # a location must not end up in a log line
        return "Anchor(source=%r)" % self.source


def valid_point(lat: Any, lon: Any) -> bool:
    return (
        isinstance(lat, (int, float))
        and isinstance(lon, (int, float))
        and math.isfinite(lat)
        and math.isfinite(lon)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
    )


def choose_anchor(
    location: Optional[Tuple[float, float]] = None,
    lodging: Optional[Tuple[float, float]] = None,
    region: Optional[Region] = None,
) -> Anchor:
    """location (lat, lon) > lodging > the region centre. A point outside the region is
    skipped: a tourist in another city is not "near" anything Jol plans, the centre is a better
    guess."""
    region = region or default_region()
    for point, source in ((location, SOURCE_LOCATION), (lodging, SOURCE_LODGING)):
        if point and valid_point(*point) and region.contains(point[0], point[1]):
            return Anchor(point[0], point[1], source)
    return Anchor(region.centre[0], region.centre[1], SOURCE_REGION)


def lodging_point(brief: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """Coordinates of the trip's accommodation if the brief has them (it has no field for them
    yet: booking a stay will add one), else None."""
    stay = (brief or {}).get("lodging")
    if isinstance(stay, dict) and valid_point(stay.get("lat"), stay.get("lon")):
        return stay["lat"], stay["lon"]
    return None


def distance_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle distance in metres (haversine; metres-level error is irrelevant here)."""
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    d_lat, d_lon = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- opening hours

Hours = List[Tuple[int, time, time]]


def closing_time(hours: Hours, now: datetime) -> Optional[str]:
    """ "HH:MM" the place closes today if it is open at `now`; None when closed, round the clock
    or without hours."""
    if not service.is_open_now(hours, now):
        return None
    local = now.astimezone(default_region().tz)
    today, yesterday = local.weekday(), (local.weekday() - 1) % 7
    t = local.time().replace(second=0, microsecond=0, tzinfo=None)
    for weekday, opens, closes in hours:
        round_clock = opens == time(0, 0) and closes == time(23, 59)
        if round_clock:
            continue
        if weekday == today and service._covers(opens, closes, t):
            return closes.strftime("%H:%M")
        if weekday == yesterday and closes <= opens and t < closes:
            return closes.strftime("%H:%M")
    return None


def is_round_the_clock(hours: Hours, now: datetime) -> bool:
    local = now.astimezone(default_region().tz)
    return any(w == local.weekday() and o == time(0, 0) and c == time(23, 59) for w, o, c in hours)


# ---------------------------------------------------------------- data for the candidates

PLACE_EXTRAS = """
SELECT p.id, p.address_ru, p.address_en, p.avg_check_kzt, p.entry_price_kzt,
       c.name_ru AS category_ru, c.name_en AS category_en
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.id = ANY(%(ids)s::uuid[])
"""

PLACE_HOURS_OF = """
SELECT place_id, weekday, opens, closes FROM place_hours WHERE place_id = ANY(%(ids)s::uuid[])
"""


async def load_extras(conn, ids: List[Any]) -> Tuple[Dict[Any, Dict[str, Any]], Dict[Any, Hours]]:
    if not ids:
        return {}, {}
    extras = {r["id"]: r for r in await fetch_all(conn, PLACE_EXTRAS, {"ids": ids})}
    hours: Dict[Any, Hours] = {}
    for r in await fetch_all(conn, PLACE_HOURS_OF, {"ids": ids}):
        hours.setdefault(r["place_id"], []).append((r["weekday"], r["opens"], r["closes"]))
    return extras, hours


# ---------------------------------------------------------------- scoring and signals


def price_level(avg_check_kzt: Optional[int]) -> Optional[int]:
    if avg_check_kzt is None:
        return None
    return 1 if avg_check_kzt < PRICE_CHEAP_KZT else 2 if avg_check_kzt < PRICE_MID_KZT else 3


def score(
    popularity: int,
    dist_m: float,
    open_now: Optional[bool],
    has_hours: bool,
    has_address: bool,
    tier: Optional[int] = None,
) -> float:
    pop = min(max(popularity, 0), POPULARITY_REF) / POPULARITY_REF
    near = 1 / (1 + (dist_m / DISTANCE_HALF_M) ** 2)
    opened = OPEN_UNKNOWN if open_now is None else (1.0 if open_now else 0.0)
    complete = (int(has_hours) + int(has_address)) / 2
    quality = W_POPULARITY * pop + W_OPEN * opened + W_COMPLETE * complete
    total = W_DISTANCE * near + quality * (QUALITY_FLOOR + (1 - QUALITY_FLOOR) * near)
    if open_now is False:
        total *= CLOSED_FACTOR
    if tier is not None:
        total += TIER_STEP * DISH_TIER_BONUS.get(tier, 0)
    return total


def _short(text: Optional[str]) -> Optional[str]:
    text = " ".join((text or "").split())
    if not text:
        return None
    return text if len(text) <= ADDRESS_CHARS else text[: ADDRESS_CHARS - 1].rstrip() + "…"


def rank(
    rows: Iterable[Dict[str, Any]],
    extras: Dict[Any, Dict[str, Any]],
    hours: Dict[Any, Hours],
    anchor: Anchor,
    now: datetime,
    locale: str,
    limit: int,
    sort: bool = True,
) -> List[Dict[str, Any]]:
    """Rows (search rows: id, lat, lon, popularity, optional `tier`) -> the top `limit` as
    `{"row": row, "signals": {...}}`, best first. `sort=False` keeps the incoming order (a search
    by name is ordered by how well the name fits) and only attaches the signals."""
    scored = []
    for row in rows:
        place_hours = hours.get(row["id"], [])
        extra = extras.get(row["id"], {})
        dist = distance_m(anchor.lat, anchor.lon, row["lat"], row["lon"])
        opened = service.is_open_now(place_hours, now) if place_hours else None
        address = _short(extra.get("address_ru" if locale == "ru" else "address_en")) or _short(
            extra.get("address_en" if locale == "ru" else "address_ru")
        )
        total = score(
            row["popularity"] or 0,
            dist,
            opened,
            bool(place_hours),
            address is not None,
            row.get("tier"),
        )
        step = LOCATION_ROUND_M if anchor.source == SOURCE_LOCATION else 50
        signals: Dict[str, Any] = {"distance_m": max(step, int(round(dist / step)) * step)}
        if row["popularity"]:
            signals["popularity"] = int(row["popularity"])
        if opened is not None:
            signals["open_now"] = opened
            if opened:
                if is_round_the_clock(place_hours, now):
                    signals["open_24h"] = True
                else:
                    closes = closing_time(place_hours, now)
                    if closes:
                        signals["closes_at"] = closes
        level = price_level(extra.get("avg_check_kzt"))
        if level is not None:
            signals["price_level"] = level
            signals["avg_check_kzt"] = int(extra["avg_check_kzt"])
        if extra.get("entry_price_kzt") is not None:
            signals["entry_kzt"] = int(extra["entry_price_kzt"])
        if address:
            signals["address"] = address
        category = extra.get("category_ru" if locale == "ru" else "category_en")
        if category:
            signals["category_name"] = category
        scored.append((total, row, signals))
    if sort:
        scored.sort(key=lambda item: -item[0])
    return [{"row": row, "signals": signals} for _, row, signals in scored[:limit]]
