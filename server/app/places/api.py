"""Places, categories and curated routes (read-only, public). Prefix /v1."""

from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.bookings import service as bookings_service
from app.crowd import service as crowd_service
from app.db import fetch_all, fetch_one
from app.errors import AppError
from app.events import service as events_service
from app.i18n import pick_locale
from app.live import clock
from app.places import schemas, service, sql
from app.providers.storage import media_url

router = APIRouter(prefix="/v1")

DEFAULT_LIMIT = 200
MAX_LIMIT = 1000
CARD_EVENTS_DAYS = 30  # events at the place shown on its card: the next month
CARD_EVENTS_LIMIT = 5


def _locale(request: Request) -> str:
    return pick_locale(request.headers.get("accept-language"))


def _summary(row: dict, locale: str) -> dict:
    name, lang = service.pick_text(row, "name", locale)
    return {
        "id": row["id"],
        "name": name or "",
        "name_lang": lang,
        "category": row["category"],
        "kind": row["kind"],
        "lat": row["lat"],
        "lon": row["lon"],
        "is_public": row["is_public"],
        "is_partner": row["is_partner"],
        "popularity": row["popularity"],
    }


def _rating(row: Optional[dict]) -> Optional[dict]:
    if not row or not row["n"]:
        return None
    return {"average": round(float(row["avg"]), 1), "count": row["n"]}


def _address(row: dict, locale: str) -> Optional[str]:
    return service.pick_text(
        row, "address", locale, ("ru", "en") if locale == "ru" else ("en", "ru")
    )[0]


def _hours(rows: list) -> list:
    return [(h["weekday"], h["opens"], h["closes"]) for h in rows]


def _geojson(items: list) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": str(i["id"]),
                "geometry": {"type": "Point", "coordinates": [i["lon"], i["lat"]]},
                "properties": {
                    k: (str(v) if k == "id" else v) for k, v in i.items() if k not in ("lat", "lon")
                },
            }
            for i in items
        ],
    }


@router.get("/places")
async def list_places(
    request: Request,
    bbox: Optional[str] = Query(None, description="west,south,east,north"),
    category: Optional[str] = Query(None, max_length=64),
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    format: str = Query("json", pattern="^(json|geojson)$"),
):
    locale = _locale(request)
    params = {
        "bbox": False,
        "west": None,
        "south": None,
        "east": None,
        "north": None,
        "category": category or None,
        "q": None,
        "pattern": None,
        "near_lat": None,
        "near_lon": None,
        "radius_m": 0,
        "limit": limit,
    }
    if bbox is not None:
        try:
            west, south, east, north = service.parse_bbox(bbox)
        except ValueError as exc:
            raise AppError(422, "validation_error", "Invalid bbox: %s" % exc) from None
        params.update(bbox=True, west=west, south=south, east=east, north=north)
    query = (q or "").strip()
    if q is not None and len(query) < 2:
        raise AppError(422, "validation_error", "q must have at least 2 characters")
    if query:
        params.update(q=query, pattern=service.like_pattern(query))
    if bbox is None and not query and not category:
        raise AppError(422, "validation_error", "Provide bbox, q or category")

    async with request.app.state.db.transaction() as conn:
        rows = await fetch_all(conn, sql.PLACES_SEARCH, params)
        ids = [r["id"] for r in rows]
        ratings = {r["place_id"]: r for r in await fetch_all(conn, sql.RATINGS_BY_PLACES, (ids,))}
        hours: dict = {}
        for h in await fetch_all(conn, sql.HOURS_BY_PLACES, (ids,)):
            hours.setdefault(h["place_id"], []).append(h)
    now = clock.now()
    items = [
        dict(
            _summary(r, locale),
            rating=_rating(ratings.get(r["id"])),
            today=service.today_block(
                _hours(hours.get(r["id"], [])), now, service.region_tz(r["lat"], r["lon"])
            ),
            address=_address(r, locale),
            logo_url=media_url(r["logo_key"]) if r["logo_key"] else None,
        )
        for r in rows
    ]
    if format == "geojson":
        return JSONResponse(_geojson(items), media_type="application/geo+json")
    return schemas.PlacesList(items=items)


@router.get("/places/{place_id}", response_model=schemas.PlaceDetail)
async def get_place(request: Request, place_id: UUID):
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        row = await fetch_one(conn, sql.PLACE_BY_ID, (place_id,))
        if row is None:
            raise AppError(404, "not_found")
        hours_rows = await fetch_all(conn, sql.PLACE_HOURS, (place_id,))
        photos = await fetch_all(conn, sql.PLACE_PHOTOS, (place_id,))
        menu = await fetch_one(conn, sql.PLACE_MENU, (place_id,))
        now = clock.now()
        crowd = await crowd_service.place_block(conn, place_id, now)  # Ш-47: None = too little data
        today = clock.local_today(now)
        event_rows = await events_service.load_events(
            conn, today, today + timedelta(days=CARD_EVENTS_DAYS), limit=CARD_EVENTS_LIMIT,
            place_id=place_id,
        )  # fmt: skip
        booking = await bookings_service.card_block(conn, place_id)  # Ш-49: None = no partner
        rating_row = await fetch_one(conn, sql.RATINGS_BY_PLACES, ([place_id],))

    name, lang = service.pick_text(row, "name", locale)
    description, _ = service.pick_text(row, "description", locale)
    address = _address(row, locale)
    hours = _hours(hours_rows)
    tz = service.region_tz(row["lat"], row["lon"])
    category = None
    if row["category"]:
        category = {
            "slug": row["category"],
            "name": row["category_name_ru"] if locale == "ru" else row["category_name_en"],
        }
    return {
        "id": row["id"],
        "name": name or "",
        "name_lang": lang,
        "names": {"ru": row["name_ru"], "en": row["name_en"], "kk": row["name_kk"]},
        "description": description,
        "category": category,
        "kind": row["kind"],
        "setting": row["setting"],
        "lat": row["lat"],
        "lon": row["lon"],
        "address": address,
        "logo_url": media_url(row["logo_key"]) if row["logo_key"] else None,
        "rating": _rating(rating_row),
        "today": service.today_block(hours, now, tz),
        "website": row["website"],
        "prices": {
            "entry_price_kzt": row["entry_price_kzt"],
            "avg_check_kzt": row["avg_check_kzt"],
            "price_per_night_kzt": row["price_per_night_kzt"],
        },
        "typical_visit_min": row["typical_visit_min"],
        "is_public": row["is_public"],
        "is_partner": row["is_partner"],
        "is_mountain": row["is_mountain"],
        "elevation_m": row["elevation_m"],
        "popularity": row["popularity"],
        "photos": [dict(p, url=media_url(p["storage_key"])) for p in photos],
        "hours": service.group_hours(hours),
        "open_now": service.is_open_now(hours, now, tz),
        "menu": menu,
        "crowd": crowd,
        "events": [events_service.event_json(r, locale) for r in event_rows],
        "booking": booking,
        "data_updated_at": row["data_updated_at"],
    }


@router.get("/categories", response_model=schemas.CategoriesList)
async def list_categories(request: Request):
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        rows = await fetch_all(conn, sql.CATEGORIES)
    return {
        "items": [
            {
                "slug": r["slug"],
                "parent": r["parent"],
                "name": r["name_ru"] if locale == "ru" else r["name_en"],
                "outdoor": r["outdoor"],
                "sort_order": r["sort_order"],
            }
            for r in rows
        ]
    }


@router.get("/curated-routes", response_model=schemas.CuratedRoutesList)
async def list_curated_routes(request: Request):
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        rows = await fetch_all(conn, sql.CURATED_ROUTES)
    items = []
    for r in rows:
        title, _ = service.pick_text(r, "title", locale)
        desc, _ = service.pick_text(r, "description", locale)
        items.append(
            {
                "id": r["id"],
                "title": title or "",
                "description": desc,
                "places_count": r["places_count"],
            }
        )
    return {"items": items}


@router.get("/curated-routes/{route_id}", response_model=schemas.CuratedRouteDetail)
async def get_curated_route(request: Request, route_id: UUID):
    locale = _locale(request)
    async with request.app.state.db.transaction() as conn:
        route = await fetch_one(conn, sql.CURATED_ROUTE_BY_ID, (route_id,))
        if route is None:
            raise AppError(404, "not_found")
        rows = await fetch_all(conn, sql.CURATED_ROUTE_ITEMS, (route_id,))
    title, _ = service.pick_text(route, "title", locale)
    desc, _ = service.pick_text(route, "description", locale)
    return {
        "id": route["id"],
        "title": title or "",
        "description": desc,
        "items": [dict(_summary(r, locale), ord=r["ord"]) for r in rows],
    }
