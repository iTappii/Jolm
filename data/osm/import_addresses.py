"""Import addresses and named buildings of Almaty from OpenStreetMap into `osm_addresses` (Ш-23c).

Usage:
    python data/osm/import_addresses.py [--pbf PATH] [--dry-run]

Used by reverse geocoding (GET /v1/geocode/reverse): the app never calls an external geocoder
(SSOT §13; Nominatim's usage policy forbids heavy application use).

Source: the shared extract data/osm/cache/kazakhstan.osm.pbf (`make osm-pbf`). Kept objects, inside
the same bbox as the places import:
  * any node or way with addr:housenumber (the street comes from addr:street);
  * any building way (building=*) that has a name (a named house, a mall), even with no number.
A way is reduced to the centroid of its nodes. Multipolygon-relation buildings are skipped (rare,
and would need area assembly); the same goes for objects without usable coordinates.

Idempotent: the whole run is one transaction. Rows are upserted by (osm_type, osm_id) from a COPY
into a temp table, and rows that vanished from the extract are deleted (this is reference data with
no user content and no place_id, TECH_PLAN rule 8 does not apply). A failed run changes nothing.

Attribution: map data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from import_places import BBOX, database_url, find_pbf, in_bbox  # noqa: E402
from import_transit import localized_names  # noqa: E402

COLUMNS = (
    "osm_type",
    "osm_id",
    "lon",
    "lat",
    "housenumber",
    "street_ru",
    "street_en",
    "street_kk",
    "name_ru",
    "name_en",
    "name_kk",
    "building",
)
MAX_TEXT = 200


def clean(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value[:MAX_TEXT] if value else None


def build_record(
    osm_type: str, osm_id: int, lon: float, lat: float, tags: Dict[str, str]
) -> Optional[tuple]:
    """A row for osm_addresses, or None when the object carries nothing worth keeping."""
    housenumber = clean(tags.get("addr:housenumber"))
    name_ru, name_en, name_kk = (
        clean(v)
        for v in localized_names(
            {k: tags.get(k) for k in ("name", "name:ru", "name:en", "name:kk")}
        )
    )
    named_building = osm_type == "way" and "building" in tags and any((name_ru, name_en, name_kk))
    if housenumber is None and not named_building:
        return None
    street_tags = {
        "name": tags.get("addr:street"),
        "name:ru": tags.get("addr:street:ru"),
        "name:en": tags.get("addr:street:en"),
        "name:kk": tags.get("addr:street:kk"),
    }
    street_ru, street_en, street_kk = (clean(v) for v in localized_names(street_tags))
    building = clean(tags.get("building"))
    if building == "yes":
        building = None
    return (
        osm_type, osm_id, lon, lat, housenumber, street_ru, street_en, street_kk,
        name_ru, name_en, name_kk, building,
    )  # fmt: skip


def extract(pbf: Path, bbox: Tuple[float, float, float, float] = BBOX) -> Iterator[tuple]:
    import osmium

    fp = (
        osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY)
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("addr:housenumber", "building"))
    )
    for obj in fp:
        tags = {t.k: t.v for t in obj.tags}
        if obj.is_node():
            if not obj.location.valid():
                continue
            osm_type, lon, lat = "node", obj.location.lon, obj.location.lat
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
            osm_type = "way"
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
        if not in_bbox(lon, lat, bbox):
            continue
        record = build_record(osm_type, obj.id, lon, lat, tags)
        if record is not None:
            yield record


def load(conn, records) -> Counter:
    """Replace the table content with `records` (upsert + delete of vanished rows). No commit."""
    stats: Counter = Counter()
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS osm_addresses_in")
        cur.execute(
            "CREATE TEMP TABLE osm_addresses_in (LIKE osm_addresses INCLUDING DEFAULTS)"
            " ON COMMIT DROP"
        )
        cur.execute("ALTER TABLE osm_addresses_in DROP COLUMN geom")
        cur.execute("ALTER TABLE osm_addresses_in ADD COLUMN lon double precision")
        cur.execute("ALTER TABLE osm_addresses_in ADD COLUMN lat double precision")
        with cur.copy("COPY osm_addresses_in (%s) FROM STDIN" % ", ".join(COLUMNS)) as copy:
            for record in records:
                copy.write_row(record)
                stats["read"] += 1
        cur.execute(
            """
            INSERT INTO osm_addresses
                (osm_type, osm_id, geom, housenumber, street_ru, street_en, street_kk,
                 name_ru, name_en, name_kk, building)
            SELECT DISTINCT ON (osm_type, osm_id)
                   osm_type, osm_id, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
                   housenumber, street_ru, street_en, street_kk, name_ru, name_en, name_kk,
                   building
            FROM osm_addresses_in
            ON CONFLICT (osm_type, osm_id) DO UPDATE SET
                geom = EXCLUDED.geom, housenumber = EXCLUDED.housenumber,
                street_ru = EXCLUDED.street_ru, street_en = EXCLUDED.street_en,
                street_kk = EXCLUDED.street_kk, name_ru = EXCLUDED.name_ru,
                name_en = EXCLUDED.name_en, name_kk = EXCLUDED.name_kk,
                building = EXCLUDED.building
            WHERE (osm_addresses.geom::geometry, osm_addresses.housenumber,
                   osm_addresses.street_ru, osm_addresses.street_en, osm_addresses.street_kk,
                   osm_addresses.name_ru, osm_addresses.name_en, osm_addresses.name_kk,
                   osm_addresses.building)
                IS DISTINCT FROM
                  (EXCLUDED.geom::geometry, EXCLUDED.housenumber, EXCLUDED.street_ru,
                   EXCLUDED.street_en, EXCLUDED.street_kk, EXCLUDED.name_ru, EXCLUDED.name_en,
                   EXCLUDED.name_kk, EXCLUDED.building)
            """
        )
        stats["upserted"] = (
            cur.rowcount
        )  # inserted or changed; unchanged rows are left alone (no bloat)
        cur.execute(
            "DELETE FROM osm_addresses a WHERE NOT EXISTS (SELECT 1 FROM osm_addresses_in i"
            " WHERE i.osm_type = a.osm_type AND i.osm_id = a.osm_id)"
        )
        stats["deleted"] = cur.rowcount
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pbf", help="path to kazakhstan .osm.pbf")
    ap.add_argument("--dry-run", action="store_true", help="parse only, do not touch the DB")
    args = ap.parse_args(argv)

    pbf = find_pbf(args.pbf)
    print(f"reading {pbf} (bbox {BBOX})", flush=True)
    records = extract(pbf)
    if args.dry_run:
        n = sum(1 for _ in records)
        print(f"dry-run: {n} address/building rows")
        return 0

    import psycopg

    with psycopg.connect(database_url()) as conn:
        stats = load(conn, records)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*), count(housenumber), count(coalesce(name_ru, name_en, name_kk)),"
                " pg_size_pretty(pg_total_relation_size('osm_addresses')) FROM osm_addresses"
            )
            total, with_number, with_name, size = cur.fetchone()
    print(
        f"osm_addresses: read {stats['read']}, upserted {stats['upserted']}, deleted "
        f"{stats['deleted']}; table now {total} rows ({with_number} with a house number, "
        f"{with_name} named), {size}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
