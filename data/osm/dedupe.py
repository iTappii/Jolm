"""Collapse duplicate OSM objects of one real-world place inside a single import (pure Python).

Two rules, both deliberately conservative:

1. Outer member of an imported relation. A multipolygon relation (a big park) is imported as
   one place; its outer way is the very same object, so a way that is an outer member of an
   imported relation of the same class is dropped in favour of the relation.
2. Same venue mapped twice. A node and a way/relation (or two nodes) with the same normalized
   name, the same class and centres within NEAR_M metres are one place; the way/relation wins
   (better geometry), then the lowest id. Chain branches with the same name farther apart
   than NEAR_M stay separate places. Way+way pairs are never merged (two buildings).

The dropped object's useful tags (names, hours, website, address, elevation) are copied into
the survivor when the survivor lacks them. The caller also merges already-imported DB rows
(data/osm/merge.py).
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from tag_mapping import CATEGORY_DEFAULTS, classify

NEAR_M = 50.0

# categories that are the same kind of object for dedupe purposes: a park mapped as a garden,
# a cafe whose cuisine is tagged on only one of its two OSM objects (coffee vs cafe_caucasian).
# Hotels, malls, landmarks etc. stay apart: a hotel and its restaurant are different places.
CLASS_GROUP = {
    "park": "green",
    "garden": "green",
    "landmark": "heritage",
    "monument": "heritage",
    "historic": "heritage",
    **{
        slug: "food"
        for slug in CATEGORY_DEFAULTS
        if slug in ("restaurant", "coffee", "bakery", "bar") or slug.startswith("cafe_")
    },
}

NAME_KEYS = ("name", "name:ru", "name:en", "name:kk", "int_name", "alt_name", "official_name")
MERGE_TAG_PREFIXES = (
    "name", "addr:", "opening_hours", "website", "contact:website", "ele", "cuisine",
)  # fmt: skip
_PRIORITY = {"relation": 0, "way": 1, "node": 2}

Key = Tuple[str, int]
# (osm_type, osm_id, lon, lat, tags)
Rec = Tuple[str, int, float, float, Dict[str, str]]


def normalize_name(value: str) -> str:
    v = value.casefold().replace("ё", "е")
    v = re.sub(r"[\W_]+", " ", v, flags=re.UNICODE)
    return " ".join(v.split())


def name_set(tags: Mapping[str, str]) -> Set[str]:
    out = set()
    for key in NAME_KEYS:
        value = tags.get(key)
        if value:
            for part in value.split(";"):
                n = normalize_name(part)
                if n:
                    out.add(n)
    return out


def class_of(tags: Mapping[str, str]) -> Optional[str]:
    spec = classify(tags)
    if spec is None:
        return None
    return CLASS_GROUP.get(spec.category, spec.category)


def distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _fill_tags(survivor: Dict[str, str], dropped: Mapping[str, str]) -> None:
    """Copy tags the survivor lacks (only safe descriptive keys, never category-defining ones)."""
    for key, value in dropped.items():
        if key.startswith(MERGE_TAG_PREFIXES) and key not in survivor and value:
            survivor[key] = value


def dedupe(
    records: Iterable[Rec], relation_outers: Mapping[int, Set[int]]
) -> Tuple[List[Rec], Dict[Key, Key], Dict[str, int]]:
    """Return (kept records, {dropped key: survivor key}, counters)."""
    recs: Dict[Key, Rec] = {(r[0], r[1]): r for r in records}
    tags: Dict[Key, Dict[str, str]] = {k: dict(r[4]) for k, r in recs.items()}
    drops: Dict[Key, Key] = {}
    counts = {"outer_member": 0, "same_venue": 0}

    # rule 1: outer member ways of imported relations
    way_to_rel: Dict[int, int] = {}
    for otype, oid in sorted(recs):
        if otype == "relation":
            for way_id in relation_outers.get(oid, ()):
                way_to_rel.setdefault(way_id, oid)
    for way_id, rel_id in way_to_rel.items():
        wkey, rkey = ("way", way_id), ("relation", rel_id)
        if wkey not in recs or rkey not in recs:
            continue
        cw, cr = class_of(recs[wkey][4]), class_of(recs[rkey][4])
        if cw is not None and cw == cr:
            drops[wkey] = rkey
            _fill_tags(tags[rkey], tags[wkey])
            counts["outer_member"] += 1

    # rule 2: node + way/relation (or node + node) of the same venue within NEAR_M
    alive = sorted((k for k in recs if k not in drops), key=lambda k: (_PRIORITY[k[0]], k[1]))
    info = {k: (name_set(recs[k][4]), class_of(recs[k][4])) for k in alive}
    grid: Dict[Tuple[int, int], List[Key]] = defaultdict(list)

    def cell(k: Key) -> Tuple[int, int]:
        return int(recs[k][3] / 0.0006), int(recs[k][2] / 0.0009)  # ~67 m lat, ~72 m lon cells

    for k in alive:
        grid[cell(k)].append(k)
    consumed: Set[Key] = set()
    for w in alive:
        if w in consumed:
            continue
        wnames, wclass = info[w]
        if not wnames or wclass is None:
            continue
        ci, cj = cell(w)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for c in grid.get((ci + di, cj + dj), ()):
                    if c == w or c in consumed or c in drops:
                        continue
                    if c[0] != "node":  # way/relation are never absorbed (only nodes are)
                        continue
                    cnames, cclass = info[c]
                    if cclass != wclass or not (wnames & cnames):
                        continue
                    if distance_m(recs[w][2], recs[w][3], recs[c][2], recs[c][3]) > NEAR_M:
                        continue
                    if _PRIORITY[w[0]] == _PRIORITY[c[0]] and w[1] > c[1]:
                        continue  # node+node: lowest id survives (w iterates ascending)
                    drops[c] = w
                    consumed.add(c)
                    _fill_tags(tags[w], tags[c])
                    counts["same_venue"] += 1

    kept = [
        (t, i, lon, lat, tags[(t, i)])
        for (t, i, lon, lat, _) in recs.values()
        if (t, i) not in drops
    ]
    return kept, drops, counts
