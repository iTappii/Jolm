"""Import the curated popular-places layer from CSV into `places` (TECH_PLAN Ш-09).

Usage: python data/seed/import_popular.py [path.csv]   (DATABASE_URL from env or .env)

- Idempotent. A row with osm_type/osm_id upserts onto that OSM object (inserting it if the OSM
  import has not run yet); a row without them is a manual place matched by (name_ru, <500 m).
- Every field set here is recorded in places.manual_override, so a later OSM re-import
  (data/osm/import_places.py) never overwrites curated values.
- Prices in the CSV are estimates; empty = unknown (OPEN(SSOT §16.2): KZT only).
- Raw parameterized SQL only (SSOT §14.1). Does not commit: the caller owns the transaction.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional

from psycopg.types.json import Jsonb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "osm"))

from merge import merge_place  # noqa: E402
from tag_mapping import CATEGORY_DEFAULTS  # noqa: E402

DEFAULT_CSV = HERE / "popular_places.csv"
SETTINGS = ("indoor", "outdoor", "mixed")

# Columns written by this importer (hard-coded whitelist; also the manual_override names).
CURATED_FIELDS = (
    "name_ru", "name_en", "description_ru", "description_en", "category_id", "kind", "geom",
    "setting", "is_mountain", "elevation_m", "is_public", "popularity",
    "typical_visit_min", "entry_price_kzt", "avg_check_kzt",
)  # fmt: skip

# value expression per column (named parameters only); order follows CURATED_FIELDS
VALUE_EXPR = {
    "name_ru": "%(name_ru)s",
    "name_en": "%(name_en)s",
    "description_ru": "%(description_ru)s",
    "description_en": "%(description_en)s",
    "category_id": "(SELECT id FROM place_categories WHERE slug = %(category)s)",
    "kind": "%(kind)s",
    "geom": "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography",
    "setting": "%(setting)s",
    "is_mountain": "%(is_mountain)s",
    "elevation_m": "%(elevation_m)s",
    "is_public": "%(is_public)s",
    "popularity": "%(popularity)s",
    "typical_visit_min": "%(typical_visit_min)s",
    "entry_price_kzt": "%(entry_price_kzt)s",
    "avg_check_kzt": "%(avg_check_kzt)s",
}
assert set(VALUE_EXPR) == set(CURATED_FIELDS)

_COLUMNS = ", ".join(CURATED_FIELDS)
_VALUES = ", ".join(VALUE_EXPR[c] for c in CURATED_FIELDS)
# a field is only overwritten (and protected) when the CSV gave a value for it
_SET_EXCLUDED = ",\n    ".join(
    f"{c} = CASE WHEN %(set_{c})s THEN EXCLUDED.{c} ELSE places.{c} END" for c in CURATED_FIELDS
)
_SET_VALUES = ",\n    ".join(
    f"{c} = CASE WHEN %(set_{c})s THEN {VALUE_EXPR[c]} ELSE places.{c} END" for c in CURATED_FIELDS
)
_MERGE_OVERRIDE = """(
        SELECT coalesce(jsonb_agg(DISTINCT v), '[]'::jsonb)
        FROM jsonb_array_elements(places.manual_override || %(override)s::jsonb) AS v)"""

UPSERT_OSM = f"""
INSERT INTO places (osm_type, osm_id, {_COLUMNS}, manual_override)
VALUES (%(osm_type)s, %(osm_id)s, {_VALUES}, %(override)s)
ON CONFLICT (osm_type, osm_id) DO UPDATE SET
    {_SET_EXCLUDED},
    manual_override = {_MERGE_OVERRIDE},
    data_updated_at = now()
RETURNING id, (xmax = 0) AS inserted
"""

FIND_MANUAL = """
SELECT id FROM places
WHERE osm_id IS NULL AND name_ru = %(name_ru)s
  AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, 500)
ORDER BY id LIMIT 1
"""

INSERT_MANUAL = f"""
INSERT INTO places ({_COLUMNS}, manual_override)
VALUES ({_VALUES}, %(override)s)
RETURNING id
"""

UPDATE_MANUAL = f"""
UPDATE places SET
    {_SET_VALUES},
    manual_override = {_MERGE_OVERRIDE},
    data_updated_at = now()
WHERE id = %(id)s
"""


# A manual (osm_id IS NULL) row that the CSV now links to an OSM object: same name_ru, within 1 km.
FIND_LINKABLE_MANUAL = """
SELECT id FROM places
WHERE osm_id IS NULL AND name_ru = %(name_ru)s
  AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, 1000)
ORDER BY id LIMIT 1
"""

FIND_OSM_ROW = "SELECT id FROM places WHERE osm_type = %(osm_type)s AND osm_id = %(osm_id)s"

ATTACH_OSM_ID = """
UPDATE places SET osm_type = %(osm_type)s, osm_id = %(osm_id)s, data_updated_at = now()
WHERE id = %(id)s AND osm_id IS NULL
"""


def link_manual_to_osm(conn, rec: dict) -> str:
    """Make sure a CSV row with an OSM id does not leave a manual twin behind.

    Returns "none" (no twin), "attached" (twin got the OSM id) or "merged" (twin folded into
    the OSM row that already existed and deleted).
    """
    manual = conn.execute(FIND_LINKABLE_MANUAL, rec).fetchone()
    if not manual:
        return "none"
    existing = conn.execute(FIND_OSM_ROW, rec).fetchone()
    if not existing:
        conn.execute(ATTACH_OSM_ID, {**rec, "id": manual[0]})
        return "attached"
    merge_place(conn, existing[0], manual[0], any_row=False)
    return "merged"


class CsvError(ValueError):
    pass


def _opt(row: Dict[str, str], key: str) -> Optional[str]:
    value = (row.get(key) or "").strip()
    return value or None


def _int(row: Dict[str, str], key: str, line: int, required: bool = False) -> Optional[int]:
    value = _opt(row, key)
    if value is None:
        if required:
            raise CsvError(f"line {line}: {key} is required")
        return None
    try:
        return int(value)
    except ValueError:
        raise CsvError(f"line {line}: {key}={value!r} is not an integer") from None


def _bool(row: Dict[str, str], key: str, line: int) -> bool:
    value = (_opt(row, key) or "0").lower()
    if value in ("1", "true", "yes"):
        return True
    if value in ("0", "false", "no"):
        return False
    raise CsvError(f"line {line}: {key}={value!r} is not a boolean")


def parse_rows(path: Path) -> List[dict]:
    """Read and validate the CSV (comment lines starting with '#' are skipped)."""
    with open(path, encoding="utf-8", newline="") as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = []
    for n, row in enumerate(csv.DictReader(lines), start=1):
        if not (_opt(row, "name_ru") or _opt(row, "name_en")):
            raise CsvError(f"row {n}: a name is required")
        slug = _opt(row, "category")
        if slug not in CATEGORY_DEFAULTS:
            raise CsvError(f"row {n}: unknown category {slug!r}")
        setting = _opt(row, "setting")
        if setting not in SETTINGS:
            raise CsvError(f"row {n}: setting must be one of {SETTINGS}, got {setting!r}")
        visit = _int(row, "typical_visit_min", n, required=True)
        if visit <= 0:
            raise CsvError(f"row {n}: typical_visit_min must be > 0")
        osm_type, osm_id = _opt(row, "osm_type"), _int(row, "osm_id", n)
        if (osm_type is None) != (osm_id is None) or osm_type not in (
            None,
            "node",
            "way",
            "relation",
        ):
            raise CsvError(f"row {n}: osm_type/osm_id must be given together (node|way|relation)")
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            raise CsvError(f"row {n}: lat/lon are required numbers") from None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise CsvError(f"row {n}: lat/lon out of range")
        rec = {
            "osm_type": osm_type, "osm_id": osm_id, "lat": lat, "lon": lon, "category": slug,
            "kind": CATEGORY_DEFAULTS[slug][0],
            "name_ru": _opt(row, "name_ru"), "name_en": _opt(row, "name_en"),
            "description_ru": _opt(row, "description_ru"),
            "description_en": _opt(row, "description_en"),
            "setting": setting, "is_mountain": _bool(row, "is_mountain", n),
            "elevation_m": _int(row, "elevation_m", n), "is_public": _bool(row, "is_public", n),
            "popularity": _int(row, "popularity", n) or 0,
            "typical_visit_min": visit,
            "entry_price_kzt": _int(row, "entry_price_kzt", n),
            "avg_check_kzt": _int(row, "avg_check_kzt", n),
        }  # fmt: skip
        # optional values count as "set" only when the CSV has them
        optional = ("name_ru", "name_en", "description_ru", "description_en", "elevation_m",
                    "entry_price_kzt", "avg_check_kzt")  # fmt: skip
        fields = [c for c in CURATED_FIELDS if c not in optional or rec[c] is not None]
        for c in CURATED_FIELDS:
            rec[f"set_{c}"] = c in fields
        rec["override"] = Jsonb(fields)
        rows.append(rec)
    return rows


def import_csv(conn, path: Path = DEFAULT_CSV) -> Dict[str, int]:
    """Upsert all CSV rows. Returns counts; the caller commits."""
    stats = {"inserted": 0, "updated": 0}
    for rec in parse_rows(Path(path)):
        if rec["osm_type"]:
            linked = link_manual_to_osm(conn, rec)
            if linked != "none":
                stats[linked] = stats.get(linked, 0) + 1
            row = conn.execute(UPSERT_OSM, rec).fetchone()
            stats["inserted" if row[1] else "updated"] += 1
            continue
        found = conn.execute(FIND_MANUAL, rec).fetchone()
        if found:
            conn.execute(UPDATE_MANUAL, {**rec, "id": found[0]})
            stats["updated"] += 1
        else:
            conn.execute(INSERT_MANUAL, rec)
            stats["inserted"] += 1
    return stats


if __name__ == "__main__":
    import psycopg
    from load_seed import database_url

    with psycopg.connect(database_url()) as c:
        print(import_csv(c, Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV))
