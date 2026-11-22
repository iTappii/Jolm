"""Are two records one real-world place? Pure functions (Ш-58): distance, names, category group.

Used when an Overture / Foursquare record meets an existing place, and by the cross-source pass
that folds duplicates with merge_place. Conservative on purpose: a false merge loses a place,
a missed one only shows a duplicate.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, Optional, Set

from dedupe import CLASS_GROUP, distance_m, normalize_name  # noqa: F401  (distance_m re-exported)

NEAR_M = 100.0  # same venue: points of two datasets are usually within a few dozen metres
NEAR_GREEN_M = 400.0  # parks and gardens: a point of one dataset, the centre of the other
RATIO = 0.85

GROUPS = {
    **CLASS_GROUP,
    "hotel": "lodging",
    "hostel": "lodging",
    "guest_house": "lodging",
    "museum": "museum",
    "gallery": "museum",
}

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ә": "a", "і": "i", "ң": "n", "ғ": "g", "ү": "u", "ұ": "u", "қ": "k", "ө": "o", "һ": "h",
}  # fmt: skip

# words that say what a place is, not which one (RU/KK/EN, already transliterated)
GENERIC = {
    "cafe", "kafe", "restaurant", "restoran", "bar", "pub", "pab", "hotel", "otel",
    "hostel", "khostel", "coffee", "kofe", "kofeyna", "park", "muzey", "museum", "the", "club",
    "klub", "lounge", "lounzh", "bistro", "pizzeria", "picceriya", "stolovaya", "gostinica",
    "guest", "house", "dom", "ooo", "tou", "ip", "zhshs",
}  # fmt: skip


def transliterate(value: str) -> str:
    return "".join(_TRANSLIT.get(ch, ch) for ch in value.casefold())


def name_key(value: str) -> str:
    """Normalized, transliterated name without generic words (kept when nothing else is left)."""
    norm = transliterate(normalize_name(value))
    norm = re.sub(r"(.)\1+", r"\1", norm)  # coffee -> cofe, kofee -> kofe
    norm = norm.replace("c", "k").replace("ph", "f").replace("w", "v")
    tokens = norm.split()
    kept = [t for t in tokens if t not in GENERIC]
    return " ".join(kept or tokens)


def name_keys(values: Iterable[Optional[str]]) -> Set[str]:
    return {k for v in values if v for k in [name_key(v)] if k}


def names_similar(a: Set[str], b: Set[str]) -> bool:
    for x in a:
        for y in b:
            if x == y:
                return True
            short, long_ = (x, y) if len(x) <= len(y) else (y, x)
            if len(short) >= 5 and short in long_.split():
                return True
            if min(len(x), len(y)) >= 5 and SequenceMatcher(None, x, y).ratio() >= RATIO:
                return True
    return False


def group_of(category: Optional[str]) -> Optional[str]:
    return GROUPS.get(category, category) if category else None


def radius_for(category: Optional[str]) -> float:
    return NEAR_GREEN_M if group_of(category) == "green" else NEAR_M


def same_place(
    names_a: Set[str], cat_a: Optional[str], names_b: Set[str], cat_b: Optional[str], dist: float
) -> bool:
    """Close enough, similar name, compatible category (an unknown category matches any)."""
    ga, gb = group_of(cat_a), group_of(cat_b)
    if ga and gb and ga != gb:
        return False
    if dist > max(radius_for(cat_a), radius_for(cat_b)):
        return False
    return bool(names_a and names_b and names_similar(names_a, names_b))
