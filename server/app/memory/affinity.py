"""Per-user category memory for the planner, computed on read (no table to keep in sync).

Rejected types (SSOT §8: shown LESS often, never excluded):

    penalty[category] = min(MAX_PENALTY, sum over the person's signals of that category of
                            STEP[signal] * 0.5 ** (age_days / HALF_LIFE_DAYS))

`removed` counts 0.30, `replaced` 0.20 (the person still wanted something there). Signals fade:
a signal loses half its weight every 120 days, so a taste that was only a mood stops mattering.
The penalty is capped at 0.6, so the score of such a place drops by at most
W_MEMORY * 0.6 = 1.2 points (an interest match is worth 3, a full popularity 2): the weight has
a floor, never zero. Only the newest SIGNAL_LIMIT signals are read. The planner takes the max of
the penalties of a place's category and its group.

Favourites (SSOT §11.5 [предложено]): a favourite place gets W_FAVORITE_PLACE, a place whose
category holds at least one favourite gets W_FAVORITE_CATEGORY (instead, not on top). Both are
small next to an interest match; must-have places are never scored at all, so they always win.

Why on read and not an `user_category_affinity` table: the signals table is small per person
(capped here), the formula can change without a data migration, and there is no second copy that
could drift when a signal is added, merged (`merge_place`) or the account deleted.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Mapping, Set
from uuid import UUID

from app.db import fetch_all
from app.live import clock

SIGNAL_STEP = {"removed": 0.30, "replaced": 0.20}
HALF_LIFE_DAYS = 120.0
MAX_PENALTY = 0.6
SIGNAL_LIMIT = 300

W_FAVORITE_PLACE = 0.8
W_FAVORITE_CATEGORY = 0.3

SIGNALS = """
SELECT category_slug, signal, created_at FROM user_place_signals
WHERE user_id = %s AND category_slug IS NOT NULL
ORDER BY created_at DESC LIMIT %s
"""
FAVORITES = """
SELECT f.place_id, c.slug AS category
FROM user_favorites f
JOIN places p ON p.id = f.place_id AND p.status = 'active'
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE f.user_id = %s
"""


@dataclass(frozen=True)
class Memory:
    penalties: Mapping[str, float] = field(default_factory=dict)
    favorite_places: Set[UUID] = field(default_factory=set)
    favorite_categories: Set[str] = field(default_factory=set)

    @property
    def empty(self) -> bool:
        return not (self.penalties or self.favorite_places)


NO_MEMORY = Memory()


def penalties_from_signals(rows: Iterable[Mapping], now: datetime) -> Dict[str, float]:
    total: Dict[str, float] = {}
    for row in rows:
        step = SIGNAL_STEP.get(row["signal"])
        slug = row["category_slug"]
        if step is None or not slug:
            continue
        age_days = max(0.0, (now - row["created_at"]).total_seconds() / 86400.0)
        total[slug] = total.get(slug, 0.0) + step * 0.5 ** (age_days / HALF_LIFE_DAYS)
    return {slug: round(min(MAX_PENALTY, value), 4) for slug, value in total.items()}


async def load_memory(conn, user_id: UUID) -> Memory:
    signals = await fetch_all(conn, SIGNALS, (user_id, SIGNAL_LIMIT))
    favorites = await fetch_all(conn, FAVORITES, (user_id,))
    return Memory(
        penalties=penalties_from_signals(signals, clock.now()),
        favorite_places={row["place_id"] for row in favorites},
        favorite_categories={row["category"] for row in favorites if row["category"]},
    )
