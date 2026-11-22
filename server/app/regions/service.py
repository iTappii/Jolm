"""Regions from the database, cached in the process (they change with a migration, not at runtime).

`default_region()` is synchronous on purpose: the planner, clocks and prompts need it everywhere,
also in code that has no connection. Until `refresh` has run it returns the built-in seed (same
values as migration 0029). The API process and the worker call `refresh` at startup.
"""

from typing import Dict, List, Optional

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.regions.model import Region
from app.regions.seed import ALMATY

_cache: Optional[Dict[str, Region]] = None

COLUMNS = """
SELECT id, name_ru, name_en, timezone, currency, languages, centre_lat, centre_lon, camera_zoom,
       is_default, ST_XMin(boundary) AS west, ST_YMin(boundary) AS south,
       ST_XMax(boundary) AS east, ST_YMax(boundary) AS north
FROM regions
"""
LOAD = COLUMNS + "ORDER BY is_default DESC, id"

# Smallest region covering the point; the boundary itself (not the box) decides.
FOR_POINT = (
    COLUMNS
    + """
WHERE ST_Covers(boundary, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326))
ORDER BY ST_Area(boundary), id
LIMIT 1
"""
)


def _from_row(row) -> Region:
    return Region(
        id=row["id"],
        name_ru=row["name_ru"],
        name_en=row["name_en"],
        timezone=row["timezone"],
        currency=row["currency"],
        languages=tuple(row["languages"]),
        centre=(row["centre_lat"], row["centre_lon"]),
        zoom=row["camera_zoom"],
        bbox=(row["west"], row["south"], row["east"], row["north"]),
        is_default=row["is_default"],
    )


async def load_regions(conn: AsyncConnection) -> List[Region]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(LOAD)
        return [_from_row(row) for row in await cur.fetchall()]


async def refresh(conn: AsyncConnection) -> List[Region]:
    """Reload the process cache. An empty table keeps the seed, so a bare database still starts."""
    global _cache
    regions = await load_regions(conn)
    _cache = {r.id: r for r in regions} if regions else None
    return regions


def reset_cache() -> None:
    global _cache
    _cache = None


def all_regions() -> List[Region]:
    if _cache is None:
        return [ALMATY]
    return sorted(_cache.values(), key=lambda r: (not r.is_default, r.id))


def default_region() -> Region:
    regions = all_regions()
    for region in regions:
        if region.is_default:
            return region
    return regions[0]


def get_region(region_id: str) -> Optional[Region]:
    return next((r for r in all_regions() if r.id == region_id), None)


async def region_for_point(conn: AsyncConnection, lat: float, lon: float) -> Optional[Region]:
    """The region whose boundary covers the point, or None outside every region."""
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(FOR_POINT, {"lat": lat, "lon": lon})
        row = await cur.fetchone()
    return _from_row(row) if row else None
