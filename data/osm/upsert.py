"""Idempotent upsert of OSM places. Raw parameterized SQL (SSOT §14.1, no ORM).

Fields listed in places.manual_override (a jsonb array of column names) are never overwritten,
and neither are fields whose place_field_sources row says manual / partner / user (Ш-58). After the
upsert the fields OSM filled are recorded as source 'osm' (mark_sources).
The SQL is assembled once from a hard-coded whitelist of column names; values only via params.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

from psycopg.types.json import Jsonb  # noqa: F401  (re-exported for callers building overrides)

# column -> True when an existing non-null value is kept if OSM has no value any more
OVERWRITABLE = {
    "kind": False,
    "category_id": False,
    "name_ru": True,
    "name_en": True,
    "name_kk": True,
    "address_ru": True,
    "address_en": True,
    "website": True,
    "phone": True,
    "is_public": False,
    "is_mountain": False,
    "elevation_m": True,
    "setting": False,
    "geom": False,
}


# sources whose fields an import never overwrites (priority: manual = partner > user > open data)
PROTECTED_SOURCES = ("manual", "partner", "user")
# places columns tracked in place_field_sources (+ HOURS_FIELD below)
TRACKED_FIELDS = (
    "name_ru", "name_en", "name_kk", "address_ru", "address_en", "website", "phone", "category_id",
    "geom",
)  # fmt: skip


def _update_clause(column: str, keep_old_if_null: bool) -> str:
    new = f"EXCLUDED.{column}"
    if keep_old_if_null:
        new = f"COALESCE(EXCLUDED.{column}, places.{column})"
    protected = ", ".join(f"'{s}'" for s in PROTECTED_SOURCES)
    return (
        f"{column} = CASE WHEN places.manual_override @> '\"{column}\"'::jsonb "
        f"OR EXISTS (SELECT 1 FROM place_field_sources s WHERE s.place_id = places.id "
        f"AND s.field = '{column}' AND s.source IN ({protected})) "
        f"THEN places.{column} ELSE {new} END"
    )


UPSERT_PLACE = (
    """
INSERT INTO places (osm_type, osm_id, kind, category_id, name_ru, name_en, name_kk,
                    address_ru, address_en, website, phone, is_public, is_mountain, elevation_m,
                    setting, geom)
VALUES (%(osm_type)s, %(osm_id)s, %(kind)s,
        (SELECT id FROM place_categories WHERE slug = %(category)s),
        %(name_ru)s, %(name_en)s, %(name_kk)s, %(address_ru)s, %(address_en)s, %(website)s,
        %(phone)s, %(is_public)s, %(is_mountain)s, %(elevation_m)s, %(setting)s,
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)
ON CONFLICT (osm_type, osm_id) DO UPDATE SET
    """
    + ",\n    ".join(_update_clause(c, k) for c, k in OVERWRITABLE.items())
    + """,
    data_updated_at = now()
RETURNING id, (xmax = 0) AS inserted, manual_override
"""
)

# Record that `source` set these fields, unless the field is hand-edited (manual_override) or a
# source of the same or higher rank already owns it.
MARK_SOURCES = """
INSERT INTO place_field_sources (place_id, field, source)
SELECT p.id, f, %(source)s FROM places p, unnest(%(fields)s::text[]) AS f
WHERE p.id = %(id)s AND NOT p.manual_override @> to_jsonb(f)
ON CONFLICT (place_id, field) DO UPDATE SET source = EXCLUDED.source, updated_at = now()
WHERE source_rank(EXCLUDED.source) >= source_rank(place_field_sources.source)
"""


def mark_sources(conn, place_id, source: str, fields: Iterable[str]) -> None:
    fields = list(fields)
    if fields:
        conn.execute(MARK_SOURCES, {"id": place_id, "source": source, "fields": fields})


DELETE_HOURS = "DELETE FROM place_hours WHERE place_id = %s"
INSERT_HOURS = "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES (%s, %s, %s, %s)"

HOURS_FIELD = "hours"  # name used inside manual_override to protect hand-edited opening hours


def upsert_place(conn, record: dict, hours: Optional[Sequence[Tuple]] = None) -> Tuple[str, bool]:
    """Upsert one place (+ hours when parsed and not manually overridden).

    `record` keys: osm_type, osm_id, lon, lat, category, kind, name_*, address_*, website,
    is_public, is_mountain, elevation_m, setting. Returns (place_id, inserted).
    """
    record = {"phone": None, **record}
    row = conn.execute(UPSERT_PLACE, record).fetchone()
    place_id, inserted, override = row[0], row[1], row[2]
    filled = [f for f in TRACKED_FIELDS if f in ("category_id", "geom") or record.get(f)]
    if hours and HOURS_FIELD not in _as_list(override) and not _hours_protected(conn, place_id):
        conn.execute(DELETE_HOURS, (place_id,))
        for weekday, opens, closes in hours:
            conn.execute(INSERT_HOURS, (place_id, weekday, opens, closes))
        filled.append(HOURS_FIELD)
    mark_sources(conn, place_id, "osm", filled)
    return place_id, inserted


def _hours_protected(conn, place_id) -> bool:
    row = conn.execute(
        "SELECT 1 FROM place_field_sources WHERE place_id = %s AND field = %s AND source = ANY(%s)",
        (place_id, HOURS_FIELD, list(PROTECTED_SOURCES)),
    ).fetchone()
    return row is not None


def _as_list(value: Iterable) -> list:
    return list(value or [])
