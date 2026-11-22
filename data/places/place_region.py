"""Region boundary helpers for the importers (Ш-58): bounding box and "is this point inside".

The boundary lives in the `regions` table (Ш-57); nothing here names a city. Raw parameterized SQL.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

BBox = Tuple[float, float, float, float]  # west, south, east, north
BATCH = 20000

BBOX_SQL = (
    "SELECT ST_XMin(boundary), ST_YMin(boundary), ST_XMax(boundary), ST_YMax(boundary) "
    "FROM regions WHERE id = %s"
)
INSIDE_SQL = """
SELECT ST_Covers(r.boundary, ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326))
FROM unnest(%(lons)s::float8[], %(lats)s::float8[]) WITH ORDINALITY AS p(lon, lat, i)
CROSS JOIN regions r WHERE r.id = %(region)s ORDER BY p.i
"""


class UnknownRegion(SystemExit):
    pass


def region_bbox(conn, region_id: str) -> BBox:
    row = conn.execute(BBOX_SQL, (region_id,)).fetchone()
    if row is None:
        raise UnknownRegion(f"unknown region {region_id!r} (see table regions)")
    return (row[0], row[1], row[2], row[3])


def points_inside(conn, region_id: str, points: Sequence[Tuple[float, float]]) -> List[bool]:
    """For each (lon, lat): is it inside the region boundary (the polygon, not its box)."""
    out: List[bool] = []
    for i in range(0, len(points), BATCH):
        chunk = points[i : i + BATCH]
        rows = conn.execute(
            INSIDE_SQL,
            {
                "lons": [p[0] for p in chunk],
                "lats": [p[1] for p in chunk],
                "region": region_id,
            },
        ).fetchall()
        out.extend(bool(r[0]) for r in rows)
    return out


def filter_inside(conn, region_id: str, records: Sequence, point=lambda r: (r["lon"], r["lat"])):
    """Records whose point (default: record['lon'], record['lat']) lies inside the region."""
    flags = points_inside(conn, region_id, [point(r) for r in records])
    return [r for r, ok in zip(records, flags) if ok]
