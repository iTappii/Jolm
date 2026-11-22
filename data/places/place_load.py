"""Load Overture / Foursquare records into `places` and fold duplicates between sources (Ш-58).

Raw parameterized SQL (SSOT §14.1). For each record:
  1. its external id is known (place_external_ids) -> the same place as last time: update;
  2. else a place of another source within a few dozen metres with a similar name and a compatible
     category (match.same_place) -> the same place: link the id, fill what it lacks;
  3. else a new place.
Fields are applied by priority (db function source_rank): a manual / partner / user field is never
touched, an open-data field changes only for a source of the same or higher rank (OSM > Overture >
Foursquare), a field without a source changes only when empty. Every applied field is recorded in
place_field_sources.

`cross_dedupe` is the second line: places of different sources that ended up as separate rows (the
open data came first, OSM was imported later) are folded with merge_place (TECH_PLAN rule 8), the
OSM row surviving.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Set

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "osm"))

import place_match as match  # noqa: E402
from merge import merge_place  # noqa: E402
from tag_mapping import CATEGORY_DEFAULTS  # noqa: E402
from upsert import mark_sources  # noqa: E402

RANK = {"manual": 5, "partner": 5, "user": 4, "osm": 3, "overture": 2, "foursquare": 1}
TEXT_FIELDS = ("name_ru", "name_en", "name_kk", "address_ru", "address_en", "website", "phone")
MOUNTAIN_CATEGORIES = ("mountain", "ski")

FIND_BY_EXTERNAL = "SELECT place_id FROM place_external_ids WHERE source = %s AND external_id = %s"
NEIGHBOURS = """
SELECT p.id, p.name_ru, p.name_en, p.name_kk, c.slug,
       ST_Distance(p.geom, pt.g) AS dist,
       (p.osm_id IS NOT NULL) AS has_osm,
       coalesce((SELECT array_agg(e.source) FROM place_external_ids e WHERE e.place_id = p.id),
                ARRAY[]::text[]) AS ext
FROM (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography AS g) pt
JOIN places p ON ST_DWithin(p.geom, pt.g, %(radius)s)
LEFT JOIN place_categories c ON c.id = p.category_id
"""
CURRENT = """
SELECT name_ru, name_en, name_kk, address_ru, address_en, website, phone, manual_override,
       category_id IS NOT NULL
FROM places WHERE id = %s
"""
CURRENT_SOURCES = "SELECT field, source FROM place_field_sources WHERE place_id = %s"
INSERT_PLACE = """
INSERT INTO places (kind, category_id, name_ru, name_en, name_kk, address_ru, address_en,
                    website, phone, is_public, is_mountain, setting, geom)
VALUES (%(kind)s, (SELECT id FROM place_categories WHERE slug = %(category)s),
        %(name_ru)s, %(name_en)s, %(name_kk)s, %(address_ru)s, %(address_en)s, %(website)s,
        %(phone)s, %(is_public)s, %(is_mountain)s, %(setting)s,
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography)
RETURNING id
"""
LINK_EXTERNAL = """
INSERT INTO place_external_ids (source, external_id, place_id) VALUES (%s, %s, %s)
ON CONFLICT (source, external_id) DO UPDATE SET place_id = EXCLUDED.place_id, updated_at = now()
"""
SET_CATEGORY = (
    "UPDATE places SET category_id = (SELECT id FROM place_categories WHERE slug = %s), "
    "data_updated_at = now() WHERE id = %s"
)
SET_GEOM = (
    "UPDATE places SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, "
    "data_updated_at = now() WHERE id = %s"
)
# column names come from TEXT_FIELDS only
SET_TEXT = {
    f: f"UPDATE places SET {f} = %s, data_updated_at = now() WHERE id = %s" for f in TEXT_FIELDS
}


def _may_write(
    field: str, new_source: str, sources: Dict[str, str], override: Set[str], value
) -> bool:
    """Priority rule for one field: protected sources win, equal-or-lower open data yields."""
    if field in override:
        return False
    current = sources.get(field)
    if current is None:
        return value is None  # an unowned value is left alone; an empty one is filled
    return RANK[new_source] >= RANK[current]


def apply_record(conn, place_id, rec: Dict) -> int:
    """Write the fields of `rec` that its source may write; returns how many fields changed."""
    row = conn.execute(CURRENT, (place_id,)).fetchone()
    values = dict(zip(TEXT_FIELDS, row[:7]))
    override = {x for x in (row[7] or []) if isinstance(x, str)}
    sources = dict(conn.execute(CURRENT_SOURCES, (place_id,)).fetchall())
    source = rec["source"]
    changed: List[str] = []
    for field in TEXT_FIELDS:
        new = rec.get(field)
        if (
            new
            and values[field] != new
            and _may_write(field, source, sources, override, values[field])
        ):
            conn.execute(SET_TEXT[field], (new, place_id))
            changed.append(field)
        elif new and values[field] == new and field not in override:
            # same value: the source claims it only if it outranks the current one
            if sources.get(field) is None or RANK[source] > RANK[sources[field]]:
                changed.append(field)
    for field, current in (("category_id", "has_category" if row[8] else None), ("geom", "has")):
        if not _may_write(field, source, sources, override, current):
            continue
        if field == "category_id":
            conn.execute(SET_CATEGORY, (rec["category"], place_id))
        else:
            conn.execute(SET_GEOM, (rec["lon"], rec["lat"], place_id))
        changed.append(field)
    mark_sources(conn, place_id, source, changed)
    return len(changed)


def insert_record(conn, rec: Dict):
    kind, setting, is_public = CATEGORY_DEFAULTS[rec["category"]]
    params = dict(
        rec,
        kind=kind,
        setting=setting,
        is_public=is_public,
        is_mountain=rec["category"] in MOUNTAIN_CATEGORIES,
    )
    place_id = conn.execute(INSERT_PLACE, params).fetchone()[0]
    fields = [f for f in TEXT_FIELDS if rec.get(f)] + ["category_id", "geom"]
    mark_sources(conn, place_id, rec["source"], fields)
    return place_id


def _names(row) -> Set[str]:
    return match.name_keys(row[1:4])


def find_match(conn, rec: Dict):
    """Id of an existing place of another source that is the same place as `rec`, or None."""
    rec_names = match.name_keys([rec["name_ru"], rec["name_en"], rec["name_kk"]])
    radius = max(match.NEAR_M, match.radius_for(rec["category"]))
    best = None
    for row in conn.execute(NEIGHBOURS, {"lon": rec["lon"], "lat": rec["lat"], "radius": radius}):
        if rec["source"] in row[7]:
            continue  # one place per source id: a second record of this source is another place
        if not match.same_place(rec_names, rec["category"], _names(row), row[4], row[5]):
            continue
        if best is None or row[5] < best[1]:
            best = (row[0], row[5])
    return best[0] if best else None


def import_record(conn, rec: Dict) -> str:
    """Import one record; returns 'inserted', 'linked' (merged into a place of another source)
    or 'updated' (its id is known)."""
    found = conn.execute(FIND_BY_EXTERNAL, (rec["source"], rec["external_id"])).fetchone()
    if found:
        apply_record(conn, found[0], rec)
        conn.execute(LINK_EXTERNAL, (rec["source"], rec["external_id"], found[0]))
        return "updated"
    target = find_match(conn, rec)
    if target is not None:
        apply_record(conn, target, rec)
        conn.execute(LINK_EXTERNAL, (rec["source"], rec["external_id"], target))
        return "linked"
    place_id = insert_record(conn, rec)
    conn.execute(LINK_EXTERNAL, (rec["source"], rec["external_id"], place_id))
    return "inserted"


def import_records(conn, records: Iterable[Dict], commit_every: int = 5000) -> Counter:
    stats: Counter = Counter()
    for i, rec in enumerate(records, 1):
        stats[import_record(conn, rec)] += 1
        if i % commit_every == 0:
            conn.commit()
            print(f"  ... {i} records", flush=True)
    return stats


# --- second line: fold places of different sources that stayed separate -----------------------

CAND_TABLE = """
CREATE TEMP TABLE _cand ON COMMIT DROP AS
SELECT p.id, p.geom, p.osm_id IS NOT NULL AS has_osm, c.slug AS category,
       p.name_ru, p.name_en, p.name_kk,
       (CASE WHEN p.osm_id IS NOT NULL THEN ARRAY['osm'] ELSE ARRAY[]::text[] END)
       || coalesce((SELECT array_agg(e.source) FROM place_external_ids e
                    WHERE e.place_id = p.id), ARRAY[]::text[]) AS sources,
       (SELECT count(*) FROM place_field_sources f WHERE f.place_id = p.id) AS nfields
FROM places p
JOIN regions r ON r.id = %(region)s AND ST_Covers(r.boundary, p.geom::geometry)
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.status <> 'hidden'
"""
CAND_INDEX = "CREATE INDEX ON _cand USING gist (geom)"
PAIRS = """
SELECT a.id, a.has_osm, a.category, a.name_ru, a.name_en, a.name_kk, a.sources, a.nfields,
       b.id, b.has_osm, b.category, b.name_ru, b.name_en, b.name_kk, b.sources, b.nfields,
       ST_Distance(a.geom, b.geom) AS dist
FROM _cand a JOIN _cand b ON a.id < b.id AND ST_DWithin(a.geom, b.geom, %(radius)s)
WHERE cardinality(a.sources) > 0 AND cardinality(b.sources) > 0 AND NOT a.sources && b.sources
ORDER BY dist, a.id, b.id
"""


def _best_rank(sources: Set[str]) -> int:
    return max((RANK[s] for s in sources), default=0)


def cross_dedupe(conn, region_id: str) -> Counter:
    """Fold same-place pairs of different sources inside a region with merge_place."""
    # an indexed snapshot of the region: the self-join below would be quadratic without it
    conn.execute("DROP TABLE IF EXISTS _cand")
    conn.execute(CAND_TABLE, {"region": region_id})
    conn.execute(CAND_INDEX)
    conn.execute("ANALYZE _cand")
    rows = conn.execute(PAIRS, {"radius": match.NEAR_GREEN_M}).fetchall()
    conn.execute("DROP TABLE _cand")
    info: Dict = {}
    dropped: Set = set()
    stats: Counter = Counter()
    for r in rows:
        for pid, has_osm, cat, ru, en, kk, srcs, nfields in (r[0:8], r[8:16]):
            names = match.name_keys([ru, en, kk])
            info.setdefault(
                pid,
                {"osm": has_osm, "cat": cat, "names": names, "sources": set(srcs), "n": nfields},
            )
    for r in rows:
        a, b, dist = r[0], r[8], r[16]
        if a in dropped or b in dropped:
            continue
        ia, ib = info[a], info[b]
        if ia["sources"] & ib["sources"]:
            continue  # a source never has two rows of one place (merged earlier in this pass)
        if not match.same_place(ia["names"], ia["cat"], ib["names"], ib["cat"], dist):
            continue
        # survivor: the OSM row, then the better source, then the richer row, then the lower id
        keep, drop = sorted(
            (a, b),
            key=lambda x: (
                -int(info[x]["osm"]),
                -_best_rank(info[x]["sources"]),
                -info[x]["n"],
                str(x),
            ),
        )
        merge_place(conn, keep, drop)
        info[keep]["sources"] |= info[drop]["sources"]
        info[keep]["names"] |= info[drop]["names"]
        dropped.add(drop)
        stats["merged"] += 1
    return stats
