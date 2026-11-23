"""SQL for candidate selection. Raw, parameterized (SSOT §14.1). Only active places inside the
start-area bbox; accommodation is left to the budget/lodging step (Ш-35).

Named params: west, south, east, north (degrees), plus the ones listed per query.
"""

_COLS = """
       p.id, p.name_ru, p.name_en, c.slug AS category, pc.slug AS parent, p.kind, p.setting,
       coalesce(c.outdoor, false) AS outdoor,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.popularity, p.is_public, p.is_mountain, p.typical_visit_min,
       p.entry_price_kzt, p.avg_check_kzt
"""

_FROM_WHERE = """
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_categories pc ON pc.id = c.parent_id
WHERE p.status = 'active'
  AND p.kind <> 'accommodation'
  AND coalesce(c.slug, '') <> 'accommodation'
  AND coalesce(pc.slug, '') <> 'accommodation'
  AND p.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)::geography
"""

# params: limit. The most popular places first; the rest is ranked in Python (scoring.py).
POOL = "SELECT" + _COLS + _FROM_WHERE + "ORDER BY p.popularity DESC, p.id LIMIT %(limit)s"

# Must-have by name. params: q, pattern (escaped ILIKE pattern or NULL = no substring match),
# limit. word_similarity is pg_trgm's; `<%%` uses the trigram index.
MUST_HAVE_BY_NAME = (
    "SELECT"
    + _COLS
    + """,
       GREATEST(word_similarity(%(q)s::text, coalesce(p.name_ru, '')),
                word_similarity(%(q)s::text, coalesce(p.name_en, '')),
                word_similarity(%(q)s::text, coalesce(p.name_kk, ''))) AS sim,
       coalesce(%(pattern)s::text IS NOT NULL AND (p.name_ru ILIKE %(pattern)s::text
                                                   OR p.name_en ILIKE %(pattern)s::text
                                                   OR p.name_kk ILIKE %(pattern)s::text),
                false) AS pattern_hit
"""
    + _FROM_WHERE
    + """
  AND (p.name_ru ILIKE %(pattern)s::text OR p.name_en ILIKE %(pattern)s::text
       OR p.name_kk ILIKE %(pattern)s::text
       OR %(q)s::text <%% p.name_ru OR %(q)s::text <%% p.name_en OR %(q)s::text <%% p.name_kk)
ORDER BY sim DESC, p.popularity DESC, p.id
LIMIT %(limit)s
"""
)

# Must-have by category or group. params: slugs (text[]), limit.
MUST_HAVE_BY_CATEGORY = (
    "SELECT"
    + _COLS
    + _FROM_WHERE
    + """
  AND (c.slug = ANY(%(slugs)s::text[]) OR pc.slug = ANY(%(slugs)s::text[]))
ORDER BY p.popularity DESC, p.id
LIMIT %(limit)s
"""
)

# Opening hours of many places at once (Ш-34). params: ids (uuid[]).
# weekday 0 = Monday; closes <= opens runs past midnight; 00:00-23:59 = round the clock.
HOURS = """
SELECT place_id, weekday, opens, closes FROM place_hours
WHERE place_id = ANY(%(ids)s::uuid[])
ORDER BY place_id, weekday, opens
"""

# Lodging options (Ш-35). params: west, south, east, north. Active accommodation places only;
# `price_per_night_kzt` may be NULL (the budget step then uses a category default).
LODGING = """
SELECT p.id, p.name_ru, p.name_en, c.slug AS category,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.price_per_night_kzt, p.popularity
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_categories pc ON pc.id = c.parent_id
WHERE p.status = 'active'
  AND (p.kind = 'accommodation' OR c.slug = 'accommodation' OR pc.slug = 'accommodation')
  AND p.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)::geography
ORDER BY p.popularity DESC, p.id
LIMIT 500
"""

# Places by id for trip edits (Ш-38): no status or area filter, a place that is already in a trip
# stays editable. params: ids (uuid[]).
PLACES_BY_ID = (
    "SELECT"
    + _COLS
    + """
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_categories pc ON pc.id = c.parent_id
WHERE p.id = ANY(%(ids)s::uuid[])
"""
)

# Indoor activity places near a point (Ш-40 weather replacements). params: lat, lon, radius_m,
# taken (uuid[], places already in the trip), limit. Active, not accommodation, not food, not
# outdoor, not a mountain; `setting = 'indoor'` first, then the nearest, then the most popular.
INDOOR_NEAR = (
    "SELECT"
    + _COLS
    + _FROM_WHERE.replace(
        "AND p.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)::geography",
        "AND ST_DWithin(p.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,"
        " %(radius_m)s)",
    )
    + """
  AND coalesce(c.outdoor, false) = false
  AND coalesce(p.setting, '') <> 'outdoor'
  AND NOT p.is_mountain
  AND coalesce(c.slug, '') <> 'food' AND coalesce(pc.slug, '') <> 'food'
  AND p.id <> ALL(%(taken)s::uuid[])
ORDER BY (p.setting = 'indoor') DESC NULLS LAST,
         ST_Distance(p.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography),
         p.popularity DESC, p.id
LIMIT %(limit)s
"""
)

# One place by id for a chosen must-have (Ш-54). params: id plus the area (kept so the same
# `_COLS` shape and the same "only plannable places" rules apply as everywhere in this file).
PLACE_BY_ID = "SELECT" + _COLS + _FROM_WHERE + "  AND p.id = %(id)s\n"

# Ш-61: the place a wish names outside the start area (Charyn, Kolsai, the Yasawi mausoleum...).
# params: q (the wish), lat, lon (the known place's point), radius_m, limit. Not food, not lodging;
# the best name match first, then the nearest, then the most popular.
FAR_BY_POINT = (
    "SELECT"
    + _COLS
    + """,
       GREATEST(word_similarity(%(q)s::text, coalesce(p.name_ru, '')),
                word_similarity(%(q)s::text, coalesce(p.name_en, '')),
                word_similarity(%(q)s::text, coalesce(p.name_kk, ''))) AS sim
"""
    + _FROM_WHERE.replace(
        "AND p.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)::geography",
        "AND ST_DWithin(p.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,"
        " %(radius_m)s)",
    )
    + """
  AND coalesce(c.slug, '') <> 'food' AND coalesce(pc.slug, '') <> 'food'
ORDER BY sim DESC,
         ST_Distance(p.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography),
         p.popularity DESC, p.id
LIMIT %(limit)s
"""
)

# Lodging around a point (Ш-61 overnight points). params: lat, lon, radius_m.
LODGING_NEAR = """
SELECT p.id, p.name_ru, p.name_en, c.slug AS category,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.price_per_night_kzt, p.popularity
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_categories pc ON pc.id = c.parent_id
WHERE p.status = 'active'
  AND (p.kind = 'accommodation' OR c.slug = 'accommodation' OR pc.slug = 'accommodation')
  AND ST_DWithin(p.geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(radius_m)s)
ORDER BY p.popularity DESC, p.id
LIMIT 200
"""
