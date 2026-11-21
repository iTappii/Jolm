"""Candidate scoring and pool sizing. Pure functions: no database, no clock, no randomness.

score = W_INTEREST * interest      interest in 0..1: 1 category match, 0.5 group match,
                                   +0.5 for an outdoor place when the tourist likes outdoors
      + W_POPULARITY * popularity  popularity / 100 clipped to 0..1 (the seed uses 0..100)
      - W_MEMORY * memory          0..1, from `memory[category]` / `memory[group]` (max)
      - W_CROWD * crowd * intolerance
                                   crowd 0..1 (unknown = 0), intolerance = (4 - tolerance) / 4
      + W_EVENT * event * (1 if the tourist asked for events else EVENT_UNASKED_FACTOR)
Ties are broken by popularity, then by id, so the same input always gives the same order.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set
from uuid import UUID

from app.planner.interests import Resolved
from app.planner.model import Place

W_INTEREST = 3.0
W_POPULARITY = 2.0
W_MEMORY = 2.0  # a full penalty outweighs a full popularity score, but not an interest match
W_CROWD = 1.5
W_EVENT = 1.0
EVENT_UNASKED_FACTOR = 0.5
OUTDOOR_BONUS = 0.5
GROUP_MATCH = 0.5
DEFAULT_CROWD_TOLERANCE = 2  # brief says nothing: middle of 0..4

# Pool sizes. Activities (non-food) per day come from the pace; the pool is FACTOR times what the
# days can hold so that the day layout (Ш-34) has room to drop places that do not fit hours or
# geography. Food: lunch and dinner every day, with the same slack.
ACTIVITIES_PER_DAY = {"calm": 3, "normal": 4, "dense": 6}
DEFAULT_PACE = "normal"
POOL_FACTOR = 1.5
MEALS_PER_DAY = 2
MAX_ACTIVITY_POOL = 250
MAX_FOOD_POOL = 150
MAX_CATEGORY_SHARE = 0.4  # of a pool; stops 100 monuments from filling the plan
MIN_CATEGORY_CAP = 2


@dataclass(frozen=True)
class Score:
    total: float
    interest: float
    popularity: float
    memory: float
    crowd: float
    event: float


@dataclass(frozen=True)
class PoolSizes:
    activities: int
    food: int


def pool_sizes(days: int, pace: Optional[str]) -> PoolSizes:
    """3/4/6 activities a day (calm/normal/dense) and 2 meals a day, times 1.5, capped.

    Examples: 3 days normal -> 18 activities + 9 food; 7 days dense -> 63 + 21;
    14 days calm -> 63 + 42; 60 days dense -> 250 + 150 (caps).
    """
    per_day = ACTIVITIES_PER_DAY.get(pace or DEFAULT_PACE, ACTIVITIES_PER_DAY[DEFAULT_PACE])
    days = max(1, days)
    return PoolSizes(
        activities=min(MAX_ACTIVITY_POOL, math.ceil(days * per_day * POOL_FACTOR)),
        food=min(MAX_FOOD_POOL, math.ceil(days * MEALS_PER_DAY * POOL_FACTOR)),
    )


def interest_match(place: Place, profile: Resolved) -> float:
    value = 0.0
    if place.category and place.category in profile.slugs:
        value = 1.0
    elif place.parent and place.parent in profile.slugs:
        value = GROUP_MATCH
    if profile.outdoor and (place.setting == "outdoor" or place.outdoor):
        value += OUTDOOR_BONUS
    return min(1.0, value)


def intolerance(crowd_tolerance: Optional[int]) -> float:
    tolerance = DEFAULT_CROWD_TOLERANCE if crowd_tolerance is None else crowd_tolerance
    return (4 - min(4, max(0, tolerance))) / 4


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def score_place(
    place: Place,
    profile: Resolved,
    memory: Mapping[str, float],
    crowd_level: Optional[float],
    crowd_tolerance: Optional[int],
    event_bonus: float,
) -> Score:
    interest = interest_match(place, profile)
    popularity = _clip01(place.popularity / 100.0)
    penalties = [memory.get(slug, 0.0) for slug in (place.category, place.parent) if slug]
    mem = _clip01(max(penalties, default=0.0))
    crowd = _clip01(crowd_level) if crowd_level is not None else 0.0
    event = _clip01(event_bonus)
    event_factor = 1.0 if profile.events else EVENT_UNASKED_FACTOR
    total = (
        W_INTEREST * interest
        + W_POPULARITY * popularity
        - W_MEMORY * mem
        - W_CROWD * crowd * intolerance(crowd_tolerance)
        + W_EVENT * event * event_factor
    )
    return Score(total, interest, popularity, mem, crowd, event)


@dataclass(frozen=True)
class Scored:
    place: Place
    score: Score


def rank(scored: Sequence[Scored]) -> List[Scored]:
    """Best first; deterministic tie-break by popularity, then id."""
    return sorted(scored, key=lambda s: (-s.score.total, -s.place.popularity, str(s.place.id)))


def pick_pool(
    scored: Sequence[Scored], size: int, taken: Optional[Set[UUID]] = None
) -> List[Scored]:
    """Top `size` by rank, skipping `taken` ids; one category stays under its cap while others
    are available, and only if the pool would otherwise be short are capped-out places added."""
    taken = taken or set()
    cap = max(MIN_CATEGORY_CAP, math.ceil(size * MAX_CATEGORY_SHARE))
    per_category: Dict[str, int] = {}
    chosen: List[Scored] = []
    overflow: List[Scored] = []
    for item in rank(scored):
        if len(chosen) >= size:
            break
        if item.place.id in taken:
            continue
        key = item.place.category or ""
        if per_category.get(key, 0) >= cap:
            overflow.append(item)
            continue
        per_category[key] = per_category.get(key, 0) + 1
        chosen.append(item)
    chosen.extend(overflow[: size - len(chosen)])
    return rank(chosen)
