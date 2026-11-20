"""Idempotent upsert of OSM places. Raw parameterized SQL (SSOT §14.1, no ORM).

Fields listed in places.manual_override (a jsonb array of column names) are never overwritten.
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
    "is_public": False,
    "is_mountain": False,
    "elevation_m": True,
    "setting": False,
    "geom": False,
}


def _update_clause(column: str, keep_old_if_null: bool) -> str:
    new = f"EXCLUDED.{column}"
    if keep_old_if_null:
        new = f"COALESCE(EXCLUDED.{column}, places.{column})"
    return (
        f"{column} = CASE WHEN places.manual_override @> '\"{column}\"'::jsonb "
        f"THEN places.{column} ELSE {new} END"
    )


UPSERT_PLACE = (
    """
INSERT INTO places (osm_type, osm_id, kind, category_id, name_ru, name_en, name_kk,
                    address_ru, address_en, website, is_public, is_mountain, elevation_m,
                    setting, geom)
VALUES (%(osm_type)s, %(osm_id)s, %(kind)s,
        (SELECT id FROM place_categories WHERE slug = %(category)s),
        %(name_ru)s, %(name_en)s, %(name_kk)s, %(address_ru)s, %(address_en)s, %(website)s,
        %(is_public)s, %(is_mountain)s, %(elevation_m)s, %(setting)s,
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)
ON CONFLICT (osm_type, osm_id) DO UPDATE SET
    """
    + ",\n    ".join(_update_clause(c, k) for c, k in OVERWRITABLE.items())
    + """,
    data_updated_at = now()
RETURNING id, (xmax = 0) AS inserted, manual_override
"""
)

DELETE_HOURS = "DELETE FROM place_hours WHERE place_id = %s"
INSERT_HOURS = "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES (%s, %s, %s, %s)"

HOURS_FIELD = "hours"  # name used inside manual_override to protect hand-edited opening hours


def upsert_place(conn, record: dict, hours: Optional[Sequence[Tuple]] = None) -> Tuple[str, bool]:
    """Upsert one place (+ hours when parsed and not manually overridden).

    `record` keys: osm_type, osm_id, lon, lat, category, kind, name_*, address_*, website,
    is_public, is_mountain, elevation_m, setting. Returns (place_id, inserted).
    """
    row = conn.execute(UPSERT_PLACE, record).fetchone()
    place_id, inserted, override = row[0], row[1], row[2]
    if hours and HOURS_FIELD not in _as_list(override):
        conn.execute(DELETE_HOURS, (place_id,))
        for weekday, opens, closes in hours:
            conn.execute(INSERT_HOURS, (place_id, weekday, opens, closes))
    return place_id, inserted


def _as_list(value: Iterable) -> list:
    return list(value or [])
