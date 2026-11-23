"""Ш-33: pick the places a trip can use. Deterministic; the model is not involved.

`select_candidates(conn, brief, ...)` returns a `Selection`:
- `must_haves`: one entry per must-have wish, each with at least one place, or none and the
  wish listed in `must_have_unmet`. A wish is never dropped silently.
- `activities` / `food`: scored candidates (see scoring.py) for the rest of the plan, sized by
  trip length and pace. Must-have places are always part of the selection and are not scored.
The day layout (Ш-34) decides what actually fits; this step only chooses.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Set
from uuid import UUID

from app.db import fetch_all, fetch_one
from app.memory.affinity import W_FAVORITE_CATEGORY, W_FAVORITE_PLACE, Memory
from app.places import service
from app.planner import scoring, sql
from app.planner.interests import resolve
from app.planner.model import Place, place_from_row
from app.planner.outside import OutsidePlace, outside_wish
from app.planner.signals import CrowdSource, EventBonus, UnknownCrowd, no_event_bonus
from app.regions import default_region

log = logging.getLogger(__name__)

POOL_QUERY_LIMIT = 5000  # most popular places read for scoring; a region has far fewer real sights
MUST_HAVE_FETCH = 20
NAME_ONLY_MIN_SIM = 0.4  # a name search for words that are not a known category
NAME_STRICT_MIN_SIM = 0.8  # a name found alongside a category reading of the same words
MAX_PER_MUST_HAVE = 3
FAR_PLACE_RADIUS_M = 25_000  # Ш-61: a known far place is looked up this close to its point
FAR_MIN_SIM = 0.3  # name similarity that makes a place "the one the wish names"
FAR_NEARBY_M = 15_000  # no name match: the nearest sight within this distance stands for it
MIN_NAME_CHARS = 2


@dataclass
class MustHave:
    text: str
    places: List[Place]
    how: str  # "name" | "category" | "chosen" | "outside" | "none"
    outside: Optional[OutsidePlace] = None  # Ш-56: a known place outside the v1 area


@dataclass
class Candidate:
    place: Place
    score: scoring.Score


@dataclass
class Selection:
    days: int
    pool: scoring.PoolSizes
    must_haves: List[MustHave] = field(default_factory=list)
    activities: List[Candidate] = field(default_factory=list)
    food: List[Candidate] = field(default_factory=list)
    # Ш-48: attendable events of the trip dates (rows of `events.service.EVENTS`); filled by
    # `build_plan`, empty when `select_candidates` is called alone
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def must_have_unmet(self) -> List[str]:
        # OPEN(SSOT §16.11): the planner goes on and the AI tells the person honestly.
        return [m.text for m in self.must_haves if not m.places]

    @property
    def must_have_places(self) -> List[Place]:
        """Distinct must-have places, in the order of the wishes."""
        seen: Set[UUID] = set()
        out: List[Place] = []
        for wish in self.must_haves:
            for place in wish.places:
                if place.id not in seen:
                    seen.add(place.id)
                    out.append(place)
        return out


def trip_days(brief: Mapping[str, Any]) -> int:
    start, end = brief.get("start_date"), brief.get("end_date")
    if not isinstance(start, date) or not isinstance(end, date) or end < start:
        raise ValueError("the brief needs start_date and end_date")
    return (end - start).days + 1


def places_per_must_have(days: int) -> int:
    """How many places a category wish gets: 1 for 1-2 days, 2 for 3-5, 3 from 6 days."""
    return min(MAX_PER_MUST_HAVE, 1 + days // 3)


def _area() -> Dict[str, Any]:
    west, south, east, north = default_region().bbox
    return {"west": west, "south": south, "east": east, "north": north}


async def _far_place(conn, text: str, far: OutsidePlace) -> Optional[Place]:
    """The database place for a wish that names a known place outside the start area, or None
    (then the wish is reported `outside_area`, as in Ш-56)."""
    rows = await fetch_all(
        conn,
        sql.FAR_BY_POINT,
        {"q": " ".join(text.split()), "lat": far.lat, "lon": far.lon,
         "radius_m": FAR_PLACE_RADIUS_M, "limit": 5},
    )  # fmt: skip
    if not rows:
        return None
    best = rows[0]
    if best["sim"] < FAR_MIN_SIM:  # no name match: the closest sight stands for the named place
        best = (await fetch_all(
            conn, sql.FAR_BY_POINT,
            {"q": far.name_ru, "lat": far.lat, "lon": far.lon,
             "radius_m": FAR_NEARBY_M, "limit": 5},
        ) or [None])[0]  # fmt: skip
    return place_from_row(best) if best else None


async def _resolve_must_have(
    conn, text: str, count: int, taken: Set[UUID], chosen: Optional[UUID] = None
) -> MustHave:
    """Name match first (one place), then the category reading, up to `count` places.

    Words that are a known category ("музеи", "Chinese food") only match names strongly, so
    "park" does not pick every "Park Hotel". Places already given to an earlier wish are used
    again only when nothing else fits, so every wish still gets a place.
    """
    far = None if chosen is not None else outside_wish(text)
    if far is not None:  # Ш-56: never stand in a park of the region for Charyn Canyon
        # Ш-61: a place of the country that the database knows is a real must-have (a far one)
        place = await _far_place(conn, text, far)
        if place is not None:
            return MustHave(text, [place], "name")
        return MustHave(text, [], "outside", far)
    reading = resolve([text])
    name = " ".join(text.split())
    found: List[Place] = []
    how = "none"
    if len(name) >= MIN_NAME_CHARS:
        params = dict(
            _area(),
            q=name,
            pattern=service.like_pattern(name) if reading.empty else None,
            limit=MUST_HAVE_FETCH,
        )
        rows = await fetch_all(conn, sql.MUST_HAVE_BY_NAME, params)
        min_sim = NAME_ONLY_MIN_SIM if reading.empty else NAME_STRICT_MIN_SIM
        named = [place_from_row(r) for r in rows if r["pattern_hit"] or r["sim"] >= min_sim]
        if named:
            found, how = named[:1], "name"
    if not reading.empty:
        rows = await fetch_all(
            conn,
            sql.MUST_HAVE_BY_CATEGORY,
            dict(_area(), slugs=sorted(reading.slugs), limit=MUST_HAVE_FETCH),
        )
        in_category = [place_from_row(r) for r in rows]
        have = {p.id for p in found}
        fresh = [p for p in in_category if p.id not in have and p.id not in taken]
        shared = [p for p in in_category if p.id not in have and p.id in taken]
        found = (found + fresh + shared)[:count]
        if found and how == "none":
            how = "category"
    if chosen is not None:  # Ш-54: the place the tourist picked on the live route comes first
        row = await fetch_one(conn, sql.PLACE_BY_ID, dict(_area(), id=chosen))
        if row is not None:
            found = [place_from_row(row)] + [p for p in found if p.id != chosen]
            found = found[: max(count, 1)]
            how = "chosen"
    return MustHave(text, found, how)


async def select_candidates(
    conn,
    brief: Mapping[str, Any],
    memory: Optional[Mapping[str, float]] = None,
    favorites: Optional[Memory] = None,
    crowd: Optional[CrowdSource] = None,
    event_bonus: EventBonus = no_event_bonus,
    chosen_places: Optional[Mapping[str, UUID]] = None,
) -> Selection:
    """Must-have places plus scored candidate pools for a brief with dates.

    `memory`: category slug -> penalty 0..1 (Ш-41, `memory.affinity`; none for a guest);
    `favorites`: the person's favourite places/categories for a small bonus (same source;
    only its favourite fields are read here). `crowd`: Ф15 (`ProfileCrowd`), unknown by
    default. `event_bonus`: Ф16 (`EventIndex.bonus`), zero by default. `chosen_places`: wish
    (case-folded) -> the place picked on the chat's live route (Ш-54); it comes first for that wish.
    """
    days = trip_days(brief)
    memory = memory or {}
    fav_places = favorites.favorite_places if favorites else set()
    fav_categories = favorites.favorite_categories if favorites else set()
    crowd = crowd or UnknownCrowd()
    selection = Selection(days=days, pool=scoring.pool_sizes(days, brief.get("pace")))

    taken: Set[UUID] = set()
    count = places_per_must_have(days)
    for text in brief.get("must_haves") or []:
        wish = await _resolve_must_have(
            conn, text, count, taken, (chosen_places or {}).get(text.casefold())
        )
        selection.must_haves.append(wish)
        taken.update(p.id for p in wish.places)
        if not wish.places:
            log.info("must-have %r has no place", text)

    profile = resolve(brief.get("interests") or [])
    rows = await fetch_all(conn, sql.POOL, dict(_area(), limit=POOL_QUERY_LIMIT))
    start, end = brief["start_date"], brief["end_date"]
    activities: List[scoring.Scored] = []
    food: List[scoring.Scored] = []
    for row in rows:
        place = place_from_row(row)
        if place.id in taken:
            continue
        score = scoring.score_place(
            place,
            profile,
            memory,
            crowd.level(place.id),
            brief.get("crowd_tolerance"),
            event_bonus(place, start, end),
            W_FAVORITE_PLACE
            if place.id in fav_places
            else (W_FAVORITE_CATEGORY if place.category in fav_categories else 0.0),
        )
        (food if place.is_food else activities).append(scoring.Scored(place, score))

    must_food = sum(1 for p in selection.must_have_places if p.is_food)
    must_other = len(selection.must_have_places) - must_food
    pool = selection.pool
    selection.activities = [
        Candidate(s.place, s.score)
        for s in scoring.pick_pool(activities, max(0, pool.activities - must_other))
    ]
    selection.food = [
        Candidate(s.place, s.score) for s in scoring.pick_pool(food, max(0, pool.food - must_food))
    ]
    return selection
