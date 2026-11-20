"""Representative point for polygons (pure Python, no shapely).

Rings are lists of (lon, lat). Coordinates are treated as planar (fine at city scale).
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Ring = Sequence[Point]


def _ring_area_centroid(ring: Ring) -> Tuple[float, float, float]:
    """Signed area and centroid of one ring (shoelace). Degenerate ring -> area 0."""
    a = cx = cy = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if a == 0:
        return 0.0, 0.0, 0.0
    return a / 2.0, cx / (6.0 * (a / 2.0)), cy / (6.0 * (a / 2.0))


def _in_ring(x: float, y: float, ring: Ring) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def _inside(x: float, y: float, outers: List[Ring], inners: List[Ring]) -> bool:
    return any(_in_ring(x, y, r) for r in outers) and not any(_in_ring(x, y, r) for r in inners)


def representative_point(
    outers: List[Ring], inners: Optional[List[Ring]] = None
) -> Optional[Point]:
    """Area-weighted centroid; if it falls outside the polygon (concave shape, hole), the
    middle of the widest interior stretch of the horizontal line through the centroid."""
    inners = inners or []
    outers = [r for r in outers if len(r) >= 3]
    inners = [r for r in inners if len(r) >= 3]
    if not outers:
        return None
    ax = ay = at = 0.0
    for sign, rings in ((1.0, outers), (-1.0, inners)):
        for r in rings:
            a, cx, cy = _ring_area_centroid(r)
            a = abs(a) * sign
            ax += cx * a
            ay += cy * a
            at += a
    if at <= 0:
        pts = [p for r in outers for p in r]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    cx, cy = ax / at, ay / at
    if _inside(cx, cy, outers, inners):
        return cx, cy
    xs = []
    for r in outers + inners:
        n = len(r)
        for i in range(n):
            x0, y0 = r[i]
            x1, y1 = r[(i + 1) % n]
            if (y0 > cy) != (y1 > cy):
                xs.append((x1 - x0) * (cy - y0) / (y1 - y0) + x0)
    xs.sort()
    best, best_w = None, -1.0
    for i in range(len(xs) - 1):
        mid = (xs[i] + xs[i + 1]) / 2.0
        w = xs[i + 1] - xs[i]
        if w > best_w and _inside(mid, cy, outers, inners):
            best, best_w = (mid, cy), w
    return best or outers[0][0]
