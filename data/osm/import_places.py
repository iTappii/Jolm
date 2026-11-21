"""Import Almaty (+ mountain suburbs) places from OpenStreetMap into the `places` table (Ш-08).

Usage:
    python data/osm/import_places.py [--pbf PATH] [--dry-run]

Data source: Geofabrik Kazakhstan extract at data/osm/cache/kazakhstan.osm.pbf (gitignored),
fetched by `make osm-pbf` (data/osm/fetch_pbf.sh); --pbf overrides the path.

Attribution: map data © OpenStreetMap contributors, licensed under the ODbL
(https://www.openstreetmap.org/copyright). The app shows "© OpenStreetMap" on the map and in
"About" (TECH_PLAN Ш-08). Imported places keep osm_type/osm_id, so the origin is traceable.

Geometry: a node keeps its point; a way is reduced to the centroid of its nodes; a multipolygon
relation (large parks, squares, lakes...) becomes osm_type='relation' with a point guaranteed
inside the polygon (geometry.representative_point). Areas built from closed ways are skipped
(the way itself is already imported). Unnamed objects are skipped.

Duplicates (data/osm/dedupe.py): an outer-member way of an imported relation of the same class
is not imported (the relation is the place); a node and a way/relation (or two nodes) with the
same normalized name and class within 50 m are one place. Rows of dropped objects that already
sit in the DB are folded into the survivor (data/osm/merge.py), keeping curated data.
Removed OSM objects are not deleted from our DB (status can be set to 'hidden' by hand).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dedupe import dedupe  # noqa: E402
from geometry import representative_point  # noqa: E402
from hours import parse_opening_hours  # noqa: E402
from merge import merge_place  # noqa: E402
from tag_mapping import INTERESTING_KEYS, classify  # noqa: E402
from upsert import upsert_place  # noqa: E402

# One shared extract for places, transit and Valhalla;
# fetched by data/osm/fetch_pbf.sh (`make osm-pbf`)
CACHE_PBF = HERE / "cache" / "kazakhstan.osm.pbf"

# Almaty city + mountain suburbs: Medeu (77.06, 43.16), Shymbulak (77.08, 43.13),
# Big Almaty Lake (76.99, 43.05), Kok-Zhailau (77.00, 43.09). (west, south, east, north)
BBOX = (76.70, 43.00, 77.20, 43.45)


FIND_ROW = "SELECT id FROM places WHERE osm_type = %s AND osm_id = %s"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = HERE.parent.parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    return url


def find_pbf(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    if not CACHE_PBF.exists():
        raise SystemExit(f"missing {CACHE_PBF}; run `make osm-pbf`")
    return CACHE_PBF


def in_bbox(lon: float, lat: float, bbox: Tuple[float, float, float, float] = BBOX) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _ring(ring):
    return [(n.lon, n.lat) for n in ring if n.location.valid()]


def relation_outer_members(pbf: Path) -> Dict[int, Set[int]]:
    """{multipolygon relation id: ids of its outer member ways} (cheap pass over relations)."""
    import osmium

    out: Dict[int, Set[int]] = {}
    for rel in osmium.FileProcessor(str(pbf), osmium.osm.RELATION):
        if rel.tags.get("type") not in ("multipolygon", "boundary"):
            continue
        ways = {m.ref for m in rel.members if m.type == "w" and m.role == "outer"}
        if ways:
            out[rel.id] = ways
    return out


def extract(pbf: Path, bbox: Tuple[float, float, float, float] = BBOX):
    """Yield (osm_type, osm_id, lon, lat, tags) for relevant nodes/ways/relations inside BBOX."""
    import osmium

    fp = (
        osmium.FileProcessor(str(pbf))
        .with_locations()
        .with_areas()
        .with_filter(osmium.filter.KeyFilter(*INTERESTING_KEYS))
    )
    for obj in fp:
        if obj.is_area():
            if obj.from_way():  # closed way: already handled as a way below
                continue
            tags = {t.k: t.v for t in obj.tags}
            if classify(tags) is None:
                continue
            outers = [_ring(r) for r in obj.outer_rings()]
            inners = [_ring(r) for o in obj.outer_rings() for r in obj.inner_rings(o)]
            point = representative_point(outers, inners)
            if point is not None and in_bbox(point[0], point[1], bbox):
                yield "relation", obj.orig_id(), point[0], point[1], tags
            continue
        if obj.is_node():
            osm_type = "node"
        elif obj.is_way():
            osm_type = "way"
        else:
            continue
        tags = {t.k: t.v for t in obj.tags}
        if classify(tags) is None:
            continue
        if osm_type == "node":
            if not obj.location.valid():
                continue
            lon, lat = obj.location.lon, obj.location.lat
        else:
            pts = []
            for n in obj.nodes:
                try:
                    if n.location.valid():
                        pts.append((n.location.lon, n.location.lat))
                except osmium.InvalidLocationError:
                    continue
            if not pts:
                continue
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
        if in_bbox(lon, lat, bbox):
            yield osm_type, obj.id, lon, lat, tags


def build_record(osm_type: str, osm_id: int, lon: float, lat: float, tags: Dict[str, str]):
    spec = classify(tags)
    if spec is None:
        return None, None
    record = {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "lon": lon,
        "lat": lat,
        "category": spec.category,
        "kind": spec.kind,
        "name_ru": spec.name_ru,
        "name_en": spec.name_en,
        "name_kk": spec.name_kk,
        "address_ru": spec.address_ru,
        "address_en": spec.address_en,
        "website": spec.website,
        "is_public": spec.is_public,
        "is_mountain": spec.is_mountain,
        "elevation_m": spec.elevation_m,
        "setting": spec.setting,
    }
    raw_hours = tags.get("opening_hours")
    hours = parse_opening_hours(raw_hours)
    return record, (hours, bool(raw_hours))


def merge_dropped(conn, drops: Dict[Tuple[str, int], Tuple[str, int]]) -> int:
    """Fold DB rows of dropped duplicates into their survivors; returns how many were merged."""
    merged = 0
    for (dtype, did), (ktype, kid) in sorted(drops.items()):
        drop = conn.execute(FIND_ROW, (dtype, did)).fetchone()
        keep = conn.execute(FIND_ROW, (ktype, kid)).fetchone()
        if drop and keep:
            merge_place(conn, keep[0], drop[0])
            merged += 1
    return merged


def report(conn, stats: Counter) -> None:
    print("\n=== OSM import report (© OpenStreetMap contributors, ODbL) ===")
    print(
        f"inserted: {stats['inserted']}, updated: {stats['updated']}, merged: {stats['merged']}, "
        f"hours parsed: {stats['hours_ok']}, hours unparsed: {stats['hours_unparsed']}, "
        f"no hours tag: {stats['hours_none']}"
    )
    rows = conn.execute(
        """
        SELECT coalesce(c.slug, '(none)'), count(*)
        FROM places p LEFT JOIN place_categories c ON c.id = p.category_id
        WHERE p.osm_id IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC, 1
        """
    ).fetchall()
    print("by category:")
    for slug, n in rows:
        print(f"  {slug:16s} {n}")
    total, no_ru, no_en = conn.execute(
        """
        SELECT count(*), count(*) FILTER (WHERE name_ru IS NULL),
               count(*) FILTER (WHERE name_en IS NULL)
        FROM places WHERE osm_id IS NOT NULL
        """
    ).fetchone()
    print(f"total OSM places in DB: {total}; missing RU name: {no_ru}; missing EN name: {no_en}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pbf", help="path to kazakhstan .osm.pbf")
    ap.add_argument("--dry-run", action="store_true", help="parse only, do not touch the DB")
    args = ap.parse_args(argv)

    pbf = find_pbf(args.pbf)
    print(f"reading {pbf} (bbox {BBOX})", flush=True)

    records, drops, dcounts = collect(pbf)
    print(
        f"dedupe: dropped {dcounts['outer_member']} outer-member ways, "
        f"{dcounts['same_venue']} same-venue duplicates",
        flush=True,
    )
    if args.dry_run:
        cats: Counter = Counter()
        for osm_type, osm_id, lon, lat, tags in records:
            record, hrs = build_record(osm_type, osm_id, lon, lat, tags)
            cats[record["category"]] += 1
        print(f"dry-run: {sum(cats.values())} places; by category: {dict(cats.most_common())}")
        return 0

    import psycopg

    with psycopg.connect(database_url()) as conn:
        stats = load(conn, records, drops)
        conn.commit()
        report(conn, stats)
    return 0


def collect(pbf: Path, bbox: Tuple[float, float, float, float] = BBOX):
    """Read the PBF/XML and dedupe: (records, {dropped key: survivor key}, dedupe counters)."""
    return dedupe(extract(pbf, bbox), relation_outer_members(pbf))


def load(conn, records, drops) -> Counter:
    """Upsert records and fold DB rows of dropped duplicates into survivors. Does not commit."""
    stats: Counter = Counter()
    for osm_type, osm_id, lon, lat, tags in records:
        record, (hours, had_tag) = build_record(osm_type, osm_id, lon, lat, tags)
        if had_tag:
            stats["hours_ok" if hours else "hours_unparsed"] += 1
        else:
            stats["hours_none"] += 1
        _, inserted = upsert_place(conn, record, hours)
        stats["inserted" if inserted else "updated"] += 1
    stats["merged"] = merge_dropped(conn, drops)
    return stats


if __name__ == "__main__":
    sys.exit(main())
