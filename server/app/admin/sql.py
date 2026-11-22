"""SQL for the admin panel. Raw, parameterized (SSOT §14.1). No value is ever concatenated."""

# ---------------------------------------------------------------- auth

ADMIN_BY_EMAIL = """
SELECT id, email, password_hash, disabled_at FROM admins WHERE email = %s
"""

ADMIN_INSERT = """
INSERT INTO admins (email, password_hash) VALUES (%s, %s) RETURNING id
"""

SESSION_INSERT = """
INSERT INTO admin_sessions (admin_id, token_hash, expires_at)
VALUES (%s, %s, now() + make_interval(hours => %s))
"""

# params: token_hash
SESSION_LOOKUP = """
SELECT s.id AS session_id, a.id AS admin_id, a.email::text AS email
FROM admin_sessions s
JOIN admins a ON a.id = s.admin_id
WHERE s.token_hash = %s
  AND s.revoked_at IS NULL
  AND s.expires_at > now()
  AND a.disabled_at IS NULL
"""

SESSION_REVOKE = """
UPDATE admin_sessions SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL
"""

SESSIONS_CLEANUP = """
DELETE FROM admin_sessions
WHERE expires_at < now() - interval '7 days' OR revoked_at < now() - interval '7 days'
"""

# params: email, ip, window_minutes
LOGIN_FAILURES_PAIR = """
SELECT count(*) AS n FROM admin_login_attempts
WHERE email = %s AND ip = %s AND attempted_at > now() - make_interval(mins => %s)
"""

# params: ip, window_minutes
LOGIN_FAILURES_IP = """
SELECT count(*) AS n FROM admin_login_attempts
WHERE ip = %s AND attempted_at > now() - make_interval(mins => %s)
"""

LOGIN_FAILURE_INSERT = """
INSERT INTO admin_login_attempts (email, ip) VALUES (%s, %s)
"""

LOGIN_FAILURES_CLEAR = """
DELETE FROM admin_login_attempts WHERE email = %s AND ip = %s
"""

LOGIN_ATTEMPTS_CLEANUP = """
DELETE FROM admin_login_attempts WHERE attempted_at < now() - interval '1 day'
"""

# ---------------------------------------------------------------- dashboard

COUNTS = """
SELECT (SELECT count(*) FROM places) AS places,
       (SELECT count(*) FROM place_categories) AS categories,
       (SELECT count(*) FROM curated_routes) AS routes,
       (SELECT count(*) FROM events) AS events
"""

# ---------------------------------------------------------------- places

# params: pattern|NULL (x3), category_id|NULL (x2), status|NULL (x2), limit, offset
# ILIKE '%x%' on name_ru/name_en is served by the pg_trgm GIN indexes (0002).
_PLACES_FILTER = r"""
WHERE (%s::text IS NULL OR p.name_ru ILIKE %s::text ESCAPE '\'
       OR p.name_en ILIKE %s::text ESCAPE '\' OR p.name_kk ILIKE %s::text ESCAPE '\')
  AND (%s::uuid IS NULL OR p.category_id = %s::uuid)
  AND (%s::text IS NULL OR p.status = %s::text)
"""

PLACES_LIST = (
    """
SELECT p.id, p.name_ru, p.name_en, p.name_kk, p.kind, p.status, p.popularity,
       p.entry_price_kzt, p.avg_check_kzt, p.price_per_night_kzt,
       c.name_ru AS category_name
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
"""
    + _PLACES_FILTER
    + """
ORDER BY p.popularity DESC, COALESCE(p.name_ru, p.name_en, p.name_kk), p.id
LIMIT %s OFFSET %s
"""
)

PLACES_COUNT = (
    """
SELECT count(*) AS n FROM places p
"""
    + _PLACES_FILTER
)

PLACE_GET = """
SELECT p.id, p.osm_type, p.osm_id, p.kind, p.category_id, p.name_ru, p.name_en, p.name_kk,
       p.description_ru, p.description_en, p.is_public, p.is_mountain, p.elevation_m,
       p.setting, p.typical_visit_min, p.entry_price_kzt, p.avg_check_kzt,
       p.price_per_night_kzt, p.popularity, p.status, p.manual_override,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon
FROM places p WHERE p.id = %s
"""

# Fixed column list: every column here is an admin-editable field (and a manual_override name).
PLACE_UPDATE = """
UPDATE places SET
    name_ru = %(name_ru)s, name_en = %(name_en)s, name_kk = %(name_kk)s,
    description_ru = %(description_ru)s, description_en = %(description_en)s,
    category_id = %(category_id)s, kind = %(kind)s, setting = %(setting)s,
    typical_visit_min = %(typical_visit_min)s, entry_price_kzt = %(entry_price_kzt)s,
    avg_check_kzt = %(avg_check_kzt)s, price_per_night_kzt = %(price_per_night_kzt)s,
    is_public = %(is_public)s, is_mountain = %(is_mountain)s, elevation_m = %(elevation_m)s,
    popularity = %(popularity)s, status = %(status)s,
    manual_override = %(manual_override)s::jsonb,
    data_updated_at = now()
WHERE id = %(id)s
"""

# manual_override is touched even when only hours changed
PLACE_TOUCH_OVERRIDE = """
UPDATE places SET manual_override = %s::jsonb, data_updated_at = now() WHERE id = %s
"""

PLACE_HOURS_GET = """
SELECT weekday, opens, closes FROM place_hours WHERE place_id = %s ORDER BY weekday, opens, closes
"""
PLACE_HOURS_DELETE = "DELETE FROM place_hours WHERE place_id = %s"
PLACE_HOURS_INSERT = """
INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES (%s, %s, %s, %s)
"""

PLACE_PHOTOS = """
SELECT id, storage_key, source, status, created_at FROM place_photos
WHERE place_id = %s ORDER BY created_at, id
"""
PLACE_PHOTO_INSERT = """
INSERT INTO place_photos (place_id, storage_key, source, status) VALUES (%s, %s, 'team', 'approved')
"""
PLACE_PHOTO_DELETE = "DELETE FROM place_photos WHERE id = %s AND place_id = %s"

PLACE_EXISTS = "SELECT 1 AS ok FROM places WHERE id = %s"
PLACE_PUBLIC_FLAG = "SELECT is_public FROM places WHERE id = %s FOR SHARE"

# params: pattern, limit. Light search for pickers (routes / events).
PLACE_PICKER = r"""
SELECT p.id, p.name_ru, p.name_en, p.name_kk, c.name_ru AS category_name
FROM places p
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.status <> 'closed'
  AND (p.name_ru ILIKE %s ESCAPE '\' OR p.name_en ILIKE %s ESCAPE '\'
       OR p.name_kk ILIKE %s ESCAPE '\')
ORDER BY p.popularity DESC, COALESCE(p.name_ru, p.name_en, p.name_kk), p.id
LIMIT %s
"""

PLACE_LABEL = """
SELECT id, name_ru, name_en, name_kk FROM places WHERE id = %s
"""

# ---------------------------------------------------------------- categories

CATEGORIES_LIST = """
SELECT c.id, c.slug, c.name_ru, c.name_en, c.outdoor, c.sort_order,
       p.name_ru AS parent_name, (SELECT count(*) FROM places WHERE category_id = c.id) AS places
FROM place_categories c
LEFT JOIN place_categories p ON p.id = c.parent_id
ORDER BY c.sort_order, c.slug
"""

CATEGORIES_OPTIONS = """
SELECT id, name_ru, name_en FROM place_categories ORDER BY sort_order, slug
"""

CATEGORY_GET = """
SELECT id, slug, name_ru, name_en, outdoor, sort_order FROM place_categories WHERE id = %s
"""

CATEGORY_UPDATE = """
UPDATE place_categories SET name_ru = %s, name_en = %s, outdoor = %s, sort_order = %s
WHERE id = %s
"""

CATEGORY_EXISTS = "SELECT 1 AS ok FROM place_categories WHERE id = %s"

# ---------------------------------------------------------------- curated routes

ROUTES_LIST = """
SELECT r.id, r.title_ru, r.title_en, r.status, r.created_at,
       (SELECT count(*) FROM curated_route_items i WHERE i.route_id = r.id) AS items
FROM curated_routes r ORDER BY r.created_at DESC, r.id
"""

ROUTE_GET = """
SELECT id, title_ru, title_en, description_ru, description_en, status
FROM curated_routes WHERE id = %s
"""

ROUTE_INSERT = """
INSERT INTO curated_routes (title_ru, title_en, description_ru, description_en)
VALUES (%s, %s, %s, %s) RETURNING id
"""

ROUTE_UPDATE = """
UPDATE curated_routes SET title_ru = %s, title_en = %s, description_ru = %s, description_en = %s
WHERE id = %s
"""

ROUTE_SET_STATUS = "UPDATE curated_routes SET status = %s WHERE id = %s"

ROUTE_DELETE = "DELETE FROM curated_routes WHERE id = %s"

ROUTE_ITEMS = """
SELECT i.id, i.ord, i.place_id, p.name_ru, p.name_en, p.name_kk
FROM curated_route_items i
JOIN places p ON p.id = i.place_id
WHERE i.route_id = %s ORDER BY i.ord
"""

ROUTE_ITEM_IDS = """
SELECT id, place_id, ord FROM curated_route_items WHERE route_id = %s ORDER BY ord
"""

# Item ids stay stable: no delete+reinsert. ord is unique per route, so renumbering is two-phase.
ROUTE_ITEM_APPEND = """
INSERT INTO curated_route_items (route_id, place_id, ord)
SELECT %s, %s, COALESCE(MAX(ord), 0) + 1 FROM curated_route_items WHERE route_id = %s
"""
ROUTE_ITEM_DELETE = "DELETE FROM curated_route_items WHERE id = %s AND route_id = %s"
ROUTE_ITEM_SET_ORD = "UPDATE curated_route_items SET ord = %s WHERE id = %s"
ROUTE_ITEMS_SHIFT = "UPDATE curated_route_items SET ord = ord + 1000 WHERE route_id = %s"
ROUTE_ITEMS_RENUMBER = """
UPDATE curated_route_items t SET ord = n.rn
FROM (SELECT id, row_number() OVER (ORDER BY ord)::smallint AS rn
      FROM curated_route_items WHERE route_id = %s) n
WHERE t.id = n.id
"""

ROUTE_LOCK = "SELECT id FROM curated_routes WHERE id = %s FOR UPDATE"

# ---------------------------------------------------------------- events

# starts_at/ends_at are shown and entered in the region's local time (`tz` parameter, Ш-57).
EVENTS_LIST = """
SELECT e.id, e.title_ru, e.title_en, e.is_promoted, e.sponsor, e.price_kzt,
       e.starts_at AT TIME ZONE %(tz)s AS starts_local,
       e.ends_at AT TIME ZONE %(tz)s AS ends_local,
       p.name_ru AS place_name_ru, p.name_en AS place_name_en
FROM events e
LEFT JOIN places p ON p.id = e.place_id
ORDER BY e.starts_at DESC, e.id
LIMIT 200
"""

EVENT_GET = """
SELECT e.id, e.place_id, e.title_ru, e.title_en, e.description_ru, e.description_en, e.price_kzt,
       e.category_id, e.is_promoted, e.sponsor,
       ST_Y(e.geom::geometry) AS lat, ST_X(e.geom::geometry) AS lon,
       e.starts_at AT TIME ZONE %(tz)s AS starts_local,
       e.ends_at AT TIME ZONE %(tz)s AS ends_local
FROM events e WHERE e.id = %(id)s
"""

EVENT_INSERT = """
INSERT INTO events (place_id, title_ru, title_en, description_ru, description_en, geom,
                    starts_at, ends_at, price_kzt, category_id, is_promoted, sponsor)
VALUES (%(place_id)s, %(title_ru)s, %(title_en)s, %(description_ru)s, %(description_en)s,
        CASE WHEN %(lat)s::float8 IS NULL THEN NULL
             ELSE ST_SetSRID(ST_MakePoint(%(lon)s::float8, %(lat)s::float8), 4326)::geography END,
        %(starts_at)s::timestamp AT TIME ZONE %(tz)s,
        %(ends_at)s::timestamp AT TIME ZONE %(tz)s,
        %(price_kzt)s, %(category_id)s, %(is_promoted)s, %(sponsor)s)
RETURNING id
"""

EVENT_UPDATE = """
UPDATE events SET place_id = %(place_id)s, title_ru = %(title_ru)s, title_en = %(title_en)s,
    description_ru = %(description_ru)s, description_en = %(description_en)s,
    geom = CASE WHEN %(lat)s::float8 IS NULL THEN NULL
                ELSE ST_SetSRID(ST_MakePoint(%(lon)s::float8, %(lat)s::float8), 4326)::geography
           END,
    starts_at = %(starts_at)s::timestamp AT TIME ZONE %(tz)s,
    ends_at = %(ends_at)s::timestamp AT TIME ZONE %(tz)s,
    price_kzt = %(price_kzt)s, category_id = %(category_id)s,
    is_promoted = %(is_promoted)s, sponsor = %(sponsor)s
WHERE id = %(id)s
"""

EVENT_DELETE = "DELETE FROM events WHERE id = %s"


TARIFFS_LIST = """
SELECT mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, approximate, source,
       version_id = (
           SELECT candidate.version_id
           FROM transport_tariffs AS candidate
           WHERE candidate.mode = tariff.mode AND candidate.valid_from <= %s
           ORDER BY candidate.valid_from DESC, candidate.version_id DESC
           LIMIT 1
       ) AS is_current
FROM transport_tariffs AS tariff
ORDER BY mode, valid_from DESC, version_id DESC
"""

TARIFF_INSERT = """
INSERT INTO transport_tariffs (
    mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, approximate, source
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""
