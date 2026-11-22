"""Import places of a region from OpenStreetMap, Overture Maps and Foursquare OS Places (Ш-58).

Usage:
    python data/places/run_import.py --region kazakhstan [--source osm|overture|foursquare|all]
        [--pbf PATH] [--overture PATH] [--foursquare PATH]

The region is a row of `regions`: its boundary (not a bounding box) decides which points are
imported. Sources run in the order OSM, Overture, Foursquare; then places that two sources
created separately are folded (load.cross_dedupe, merge_place). A repeated run is a monthly
refresh: ids of every source are remembered, and only fields owned by open data are updated;
manual / partner / user fields stay (see db/migrations/0031_place_sources.sql).

Attribution (shown in "About"): © OpenStreetMap contributors (ODbL); Overture Maps Foundation
(CDLA-Permissive-2.0); Foursquare OS Places (Apache-2.0).
Needs `make migrate seed` first (categories). Files: `make places-fetch` (Overture),
Foursquare needs a Hugging Face token (see docs/reviews/Ш-58.md).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "osm"))

import import_places as osm_import  # noqa: E402
import open_sources  # noqa: E402
import place_load as load  # noqa: E402
import place_region as region_mod  # noqa: E402

# the cache may live outside the checkout (shared by worktrees): PLACES_CACHE=/path
CACHE = Path(os.environ.get("PLACES_CACHE") or HERE / "cache")
SOURCES = ("osm", "overture", "foursquare")


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


def import_osm(conn, region_id: str, pbf: Path) -> Counter:
    bbox = region_mod.region_bbox(conn, region_id)
    print(f"OSM: reading {pbf}, region {region_id}, bbox {bbox}", flush=True)

    def inside(records):
        return region_mod.filter_inside(conn, region_id, records, point=lambda r: (r[2], r[3]))

    records, drops, dcounts = osm_import.collect(pbf, bbox, keep=inside)
    print(f"OSM: {len(records)} places inside the boundary; dedupe {dcounts}", flush=True)
    stats = osm_import.load(conn, records, drops)
    conn.commit()
    return stats


def import_open(conn, region_id: str, source: str, path: Path) -> Counter:
    release = path.with_suffix(".release")
    version = release.read_text().strip() if release.exists() else "unknown release"
    print(f"{source}: reading {path} ({version})", flush=True)
    reader = open_sources.read_overture if source == "overture" else open_sources.read_foursquare
    records = list(reader(path))
    inside = region_mod.filter_inside(conn, region_id, records)
    print(f"{source}: {len(records)} mapped records, {len(inside)} inside the boundary", flush=True)
    stats = load.import_records(conn, inside)
    conn.commit()
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--region", required=True, help="id from table regions")
    ap.add_argument("--source", default="all", choices=("all",) + SOURCES)
    ap.add_argument("--pbf", help="OSM extract (default data/osm/cache/kazakhstan.osm.pbf)")
    ap.add_argument("--overture", default=str(CACHE / "overture-places.parquet"))
    ap.add_argument("--foursquare", default=str(CACHE / "foursquare-places.parquet"))
    args = ap.parse_args(argv)
    wanted = SOURCES if args.source == "all" else (args.source,)

    import psycopg

    with psycopg.connect(database_url()) as conn:
        region_mod.region_bbox(conn, args.region)  # fail early on an unknown region
        for source in wanted:
            if source == "osm":
                stats = import_osm(conn, args.region, osm_import.find_pbf(args.pbf))
            else:
                path = Path(getattr(args, source))
                if not path.exists() and args.source == "all":
                    print(f"{source}: {path} not found, skipped", flush=True)
                    continue
                stats = import_open(conn, args.region, source, path)
            print(f"{source}: {dict(stats)}", flush=True)
        merged = load.cross_dedupe(conn, args.region)
        conn.commit()
        print(f"cross-source dedupe: {dict(merged)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
