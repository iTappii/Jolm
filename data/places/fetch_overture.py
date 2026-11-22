"""Download Overture Maps Places for a bounding box into the shared cache (Ш-58).

Usage:
    python data/places/fetch_overture.py --bbox 46.4 40.5 87.4 55.5 [--release 2026-11-18.0]
                                         [--out data/places/cache/overture-kz.parquet]

Source: Overture Maps Foundation, theme=places, public S3 mirror (no key or registration);
licence CDLA-Permissive-2.0 (attribution: "Overture Maps Foundation"). DuckDB reads only the
rows inside the bbox (Parquet row-group pruning on the bbox struct). The latest release is read
from the STAC catalog unless --release is given.
The result is a cache file; the importer (open_import.py) filters it by the region boundary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
# cache dir: data/places/cache (gitignored) or $PLACES_CACHE; --out overrides the file
DEFAULT_OUT = Path(os.environ.get("PLACES_CACHE") or HERE / "cache") / "overture-places.parquet"
STAC = "https://stac.overturemaps.org/catalog.json"
S3_TEMPLATE = "s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"


def latest_release() -> str:
    with urllib.request.urlopen(STAC, timeout=30) as resp:  # noqa: S310 (fixed https URL)
        return json.load(resp)["latest"]


def build_query(release: str, bbox, out: Path) -> str:
    west, south, east, north = bbox
    src = S3_TEMPLATE.format(release=release)
    return f"""
COPY (
  SELECT id, ST_X(geometry) AS lon, ST_Y(geometry) AS lat, names, taxonomy, basic_category,
         confidence, websites, phones, addresses, operating_status
  FROM read_parquet('{src}', filename = false, hive_partitioning = 1)
  WHERE bbox.xmin BETWEEN {west} AND {east} AND bbox.ymin BETWEEN {south} AND {north}
) TO '{out}' (FORMAT parquet, COMPRESSION zstd)
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), required=True)
    ap.add_argument("--release", help="Overture release, default: latest from the STAC catalog")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    import duckdb

    release = args.release or latest_release()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Overture Maps Places release {release}, bbox {args.bbox}", flush=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region = 'us-west-2'; SET s3_url_style = 'path';")
    con.execute(build_query(release, args.bbox, out))
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    print(f"saved {rows} rows, {out.stat().st_size / 1e6:.1f} MB -> {out}")
    (out.with_suffix(".release")).write_text(release + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
