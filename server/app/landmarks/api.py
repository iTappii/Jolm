"""`GET /v1/landmarks`: main places whose labels the map shows from a zoom (public, cacheable)."""

import hashlib
import json

from fastapi import APIRouter, Request, Response

from app.db import fetch_all
from app.i18n import pick_locale
from app.places import service

router = APIRouter(prefix="/v1", tags=["landmarks"])

CACHE_CONTROL = "public, max-age=3600"

# Region = the smallest one covering the point (as regions.service.FOR_POINT); rank is inside it.
LANDMARKS = """
SELECT p.id, p.name_ru, p.name_en, p.name_kk, c.slug AS category,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       l.min_zoom, l.rank, l.icon, r.id AS region
FROM landmarks l
JOIN places p ON p.id = l.place_id AND p.status = 'active'
LEFT JOIN place_categories c ON c.id = p.category_id
JOIN LATERAL (
    SELECT id FROM regions WHERE ST_Covers(boundary, p.geom::geometry)
    ORDER BY ST_Area(boundary), id LIMIT 1
) r ON true
ORDER BY r.id, l.rank, p.id
"""


@router.get("/landmarks")
async def list_landmarks(request: Request):
    locale = pick_locale(request.headers.get("accept-language"))
    async with request.app.state.db.transaction() as conn:
        rows = await fetch_all(conn, LANDMARKS)
    landmarks = [
        {
            "id": str(r["id"]),
            "name": service.pick_text(r, "name", locale)[0] or "",
            "category": r["category"],
            "lat": r["lat"],
            "lon": r["lon"],
            "min_zoom": r["min_zoom"],
            "rank": r["rank"],
            "icon": r["icon"],
            "region": r["region"],
        }
        for r in rows
    ]
    body = json.dumps({"landmarks": landmarks}, ensure_ascii=False, separators=(",", ":"))
    etag = '"%s"' % hashlib.sha256(body.encode()).hexdigest()[:32]
    headers = {"Cache-Control": CACHE_CONTROL, "ETag": etag, "Vary": "Accept-Language"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)
