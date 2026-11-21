"""Favourite places of the signed-in user (Ш-23b, SSOT §11.5). Prefix /v1, bearer auth.

    GET    /me/favorites             -> {"items": [place summary + "address", "created_at"]}
    PUT    /me/favorites/{place_id}  -> 204 (idempotent); 404 unknown or inactive place;
                                        409 `favorites_limit` at the cap (500) for a new one
    DELETE /me/favorites/{place_id}  -> 204 (idempotent, also for a place that never existed)

Guests get 401. Newest first. Names and address follow Accept-Language (ru -> ru, en, kk).
A place that was hidden or closed after being saved stays stored but is not listed.
"""

from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.auth import sessions
from app.auth.api import bearer_token
from app.db import execute, fetch_all, fetch_one
from app.errors import AppError
from app.i18n import pick_locale
from app.places import service
from app.places.api import _summary

router = APIRouter(prefix="/v1", tags=["favorites"])

MAX_FAVORITES = 500  # per user; a saved-places list, not a database

LIST = """
SELECT f.created_at,
       p.id, p.name_ru, p.name_en, p.name_kk, c.slug AS category, p.kind,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
       p.is_public, p.is_partner, p.popularity, p.address_ru, p.address_en
FROM user_favorites f
JOIN places p ON p.id = f.place_id AND p.status = 'active'
LEFT JOIN place_categories c ON c.id = p.category_id
WHERE f.user_id = %s
ORDER BY f.created_at DESC, p.id
LIMIT %s
"""
LOCK_USER = "SELECT id FROM users WHERE id = %s FOR UPDATE"
PLACE_ACTIVE = "SELECT 1 AS ok FROM places WHERE id = %s AND status = 'active'"
EXISTS = "SELECT 1 AS ok FROM user_favorites WHERE user_id = %s AND place_id = %s"
COUNT = "SELECT count(*) AS n FROM user_favorites WHERE user_id = %s"
ADD = """
INSERT INTO user_favorites (user_id, place_id) VALUES (%s, %s)
ON CONFLICT (user_id, place_id) DO NOTHING
"""
REMOVE = "DELETE FROM user_favorites WHERE user_id = %s AND place_id = %s"


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/me/favorites")
async def list_favorites(request: Request, response: Response):
    access = bearer_token(request)
    locale = pick_locale(request.headers.get("accept-language"))
    _no_store(response)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        rows = await fetch_all(conn, LIST, (user["id"], MAX_FAVORITES))
    items = []
    for row in rows:
        address, _ = service.pick_text(
            row, "address", locale, ("ru", "en") if locale == "ru" else ("en", "ru")
        )
        items.append(
            dict(_summary(row, locale), address=address, created_at=row["created_at"].isoformat())
        )
    return {"items": items}


@router.put("/me/favorites/{place_id}", status_code=204)
async def add_favorite(place_id: UUID, request: Request):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        await fetch_one(conn, LOCK_USER, (user["id"],))  # serialises the cap check per user
        if await fetch_one(conn, PLACE_ACTIVE, (place_id,)) is None:
            raise AppError(404, "not_found")
        if await fetch_one(conn, EXISTS, (user["id"], place_id)) is None:
            if (await fetch_one(conn, COUNT, (user["id"],)))["n"] >= MAX_FAVORITES:
                raise AppError(409, "favorites_limit")
            await execute(conn, ADD, (user["id"], place_id))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.delete("/me/favorites/{place_id}", status_code=204)
async def remove_favorite(place_id: UUID, request: Request):
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        await execute(conn, REMOVE, (user["id"], place_id))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
