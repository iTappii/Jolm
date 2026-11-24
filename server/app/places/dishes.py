"""Dish search (Ш-67): "бешбармак", "plov", "dim sum" -> cuisines/categories -> places.

The dictionary lives in the DB (`dishes`, `dish_aliases`, seed data/seed/dishes.sql). A place is
matched by (best first): its menu names the dish (confirmed), its name names the dish, its Jol
category is the dish's primary cuisine, its category is a related cuisine. Raw parameterized SQL
(SSOT §14.1).
"""

import re
from typing import Any, Dict, List, Optional

from app.db import fetch_all, fetch_one
from app.places import service

MIN_FUZZY_ALIAS = 6  # shorter aliases (osh, kebab...) must match as whole words, no typos
NAME_ALIAS_MIN = 4  # shorter aliases are not looked for inside place names / menus
FUZZY_THRESHOLD = 0.65

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)

TIER_MENU, TIER_NAME, TIER_CUISINE, TIER_RELATED = 0, 1, 2, 3
MATCH_NAMES = {
    TIER_MENU: "menu",
    TIER_NAME: "name",
    TIER_CUISINE: "cuisine",
    TIER_RELATED: "related_cuisine",
}


def normalize(text: str) -> str:
    """Lower case, "ё" -> "е", only letters/digits, single spaces."""
    return _NON_WORD.sub(" ", text.lower().replace("ё", "е")).strip()


# 1) the longest alias that is a whole-word run inside the query; 2) typos: close to a long alias
DISH_BY_QUERY = """
SELECT d.slug, d.name_ru, d.name_en, d.cuisines, d.categories,
       (SELECT array_agg(a2.alias) FROM dish_aliases a2
        WHERE a2.dish_slug = d.slug AND length(a2.alias) >= %(name_min)s) AS aliases,
       a.alias AS matched_alias
FROM dish_aliases a JOIN dishes d ON d.slug = a.dish_slug
WHERE (' ' || %(q)s::text || ' ') LIKE ('%% ' || a.alias || ' %%')
   OR (length(a.alias) >= %(fuzzy_min)s
       AND word_similarity(a.alias, %(q)s::text) >= %(threshold)s)
ORDER BY (' ' || %(q)s::text || ' ') LIKE ('%% ' || a.alias || ' %%') DESC,
         word_similarity(a.alias, %(q)s::text) DESC, length(a.alias) DESC
LIMIT 1
"""

# params: cats (text[], primary first), patterns (ILIKE patterns of the dish aliases), near_*,
# radius_m, limit. tier: menu names the dish / name names it / primary category / related one.
DISH_SEARCH = """
SELECT p.id, p.name_ru, p.name_en, p.name_kk, c.slug AS category, p.kind,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.is_public, p.is_partner, p.popularity,
       CASE WHEN m.payload::text ILIKE ANY(%(patterns)s::text[]) THEN 0
            WHEN p.name_ru ILIKE ANY(%(patterns)s::text[])
              OR p.name_en ILIKE ANY(%(patterns)s::text[])
              OR p.name_kk ILIKE ANY(%(patterns)s::text[]) THEN 1
            WHEN c.slug = (%(cats)s::text[])[1] THEN 2
            ELSE 3 END AS tier,
       CASE WHEN %(near_lat)s::float8 IS NULL THEN NULL
            ELSE ST_Distance(p.geom, ST_SetSRID(ST_MakePoint(%(near_lon)s::float8,
                 %(near_lat)s::float8), 4326)::geography) END AS distance_m
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_menu m ON m.place_id = p.id
WHERE p.status = 'active'
  AND (%(near_lat)s::float8 IS NULL
       OR ST_DWithin(p.geom, ST_SetSRID(ST_MakePoint(%(near_lon)s::float8,
                     %(near_lat)s::float8), 4326)::geography, %(radius_m)s::float8))
  AND (c.slug = ANY(%(cats)s::text[])
       OR m.payload::text ILIKE ANY(%(patterns)s::text[])
       OR p.name_ru ILIKE ANY(%(patterns)s::text[]) OR p.name_en ILIKE ANY(%(patterns)s::text[])
       OR p.name_kk ILIKE ANY(%(patterns)s::text[]))
ORDER BY tier, distance_m NULLS LAST, p.popularity DESC, p.id
LIMIT %(limit)s
"""


async def resolve(conn, query: str) -> Optional[Dict[str, Any]]:
    """The dish a search query is about, or None. Case-, "ё"-, punctuation-insensitive."""
    q = normalize(query)
    if len(q) < 2:
        return None
    return await fetch_one(
        conn,
        DISH_BY_QUERY,
        {
            "q": q,
            "name_min": NAME_ALIAS_MIN,
            "fuzzy_min": MIN_FUZZY_ALIAS,
            "threshold": FUZZY_THRESHOLD,
        },
    )


async def search(
    conn,
    dish: Dict[str, Any],
    limit: int,
    near: Optional[Dict[str, float]] = None,
    radius_m: float = 0,
) -> List[Dict[str, Any]]:
    params = {
        "cats": list(dish["categories"]),
        "patterns": [service.like_pattern(a) for a in dish["aliases"] or []],
        "near_lat": near["lat"] if near else None,
        "near_lon": near["lon"] if near else None,
        "radius_m": radius_m,
        "limit": limit,
    }
    return await fetch_all(conn, DISH_SEARCH, params)
