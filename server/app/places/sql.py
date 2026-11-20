"""SQL for places. Raw, parameterized (SSOT §14.1)."""

# params: west, south, east, north (lon/lat degrees), category slug or NULL, limit
# ST_MakeEnvelope in 4326 cast to geography: && uses the GIST index.
BBOX_SEARCH = """
SELECT p.id, p.name_ru, p.name_en, c.slug AS category,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.setting, p.is_public, p.popularity
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.status = 'active'
  AND p.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)::geography
  AND (%s::text IS NULL OR c.slug = %s::text)
ORDER BY p.popularity DESC, p.id
LIMIT %s
"""


# Shared column list for place summaries (pins, curated route items).
_SUMMARY_COLS = """
       p.id, p.name_ru, p.name_en, p.name_kk, c.slug AS category, p.kind,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.is_public, p.is_partner, p.popularity
"""

# params: west, south, east, north, category (x3: NULL check, slug, parent slug),
#         q (x7: NULL check, ILIKE pattern x3, word-similarity x3), q (order), limit
# `q <% name` = word_similarity above pg_trgm.word_similarity_threshold (uses the GIN trigram
# index for ru/en); the ILIKE pattern is escaped by the caller (backslash escape).
PLACES_SEARCH = (
    "SELECT"
    + _SUMMARY_COLS
    + """
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_categories pc ON pc.id = c.parent_id
WHERE p.status = 'active'
  AND (%(bbox)s::boolean IS FALSE
       OR p.geom && ST_MakeEnvelope(%(west)s, %(south)s, %(east)s, %(north)s, 4326)::geography)
  AND (%(category)s::text IS NULL OR c.slug = %(category)s::text OR pc.slug = %(category)s::text)
  AND (%(q)s::text IS NULL
       OR p.name_ru ILIKE %(pattern)s OR p.name_en ILIKE %(pattern)s OR p.name_kk ILIKE %(pattern)s
       OR %(q)s::text <%% p.name_ru OR %(q)s::text <%% p.name_en OR %(q)s::text <%% p.name_kk)
ORDER BY
  CASE WHEN %(q)s::text IS NULL THEN 0
       ELSE -GREATEST(word_similarity(%(q)s::text, coalesce(p.name_ru, '')),
                      word_similarity(%(q)s::text, coalesce(p.name_en, '')),
                      word_similarity(%(q)s::text, coalesce(p.name_kk, ''))) END,
  p.popularity DESC, p.id
LIMIT %(limit)s
"""
)

PLACE_BY_ID = """
SELECT p.id, p.name_ru, p.name_en, p.name_kk, p.description_ru, p.description_en,
       c.slug AS category, c.name_ru AS category_name_ru, c.name_en AS category_name_en,
       p.kind, p.setting,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.address_ru, p.address_en, p.website,
       p.entry_price_kzt, p.avg_check_kzt, p.price_per_night_kzt, p.typical_visit_min,
       p.is_public, p.is_partner, p.is_mountain, p.elevation_m, p.popularity,
       p.data_updated_at
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.id = %s AND p.status = 'active'
"""

PLACE_HOURS = """
SELECT weekday, opens, closes FROM place_hours
WHERE place_id = %s ORDER BY weekday, opens
"""

PLACE_PHOTOS = """
SELECT id, storage_key, source FROM place_photos
WHERE place_id = %s AND status = 'approved' ORDER BY created_at, id
"""

PLACE_MENU = "SELECT payload, source, updated_at FROM place_menu WHERE place_id = %s"

CATEGORIES = """
SELECT c.slug, p.slug AS parent, c.name_ru, c.name_en, c.outdoor, c.sort_order
FROM place_categories c
LEFT JOIN place_categories p ON p.id = c.parent_id
ORDER BY c.sort_order, c.slug
"""

# Only places that are still active are counted/listed.
CURATED_ROUTES = """
SELECT r.id, r.title_ru, r.title_en, r.description_ru, r.description_en,
       (SELECT count(*) FROM curated_route_items i JOIN places p ON p.id = i.place_id
         WHERE i.route_id = r.id AND p.status = 'active') AS places_count
FROM curated_routes r
WHERE r.status = 'published'
ORDER BY r.created_at DESC, r.id
"""

CURATED_ROUTE_BY_ID = """
SELECT id, title_ru, title_en, description_ru, description_en
FROM curated_routes WHERE id = %s AND status = 'published'
"""

CURATED_ROUTE_ITEMS = (
    "SELECT i.ord,"
    + _SUMMARY_COLS
    + """
FROM curated_route_items i
JOIN places p ON p.id = i.place_id
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE i.route_id = %s AND p.status = 'active'
ORDER BY i.ord
"""
)
