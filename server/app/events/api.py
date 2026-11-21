"""Events for the map in the trip dates (Ш-48). Public, read-only. Prefix /v1.

    GET /events?from=YYYY-MM-DD&to=YYYY-MM-DD&bbox=west,south,east,north

`from` defaults to today (Almaty), `to` to `from` + 14 days (at most 62 days apart); both are
inclusive local dates. An event is listed while it overlaps the window. Answer:

    {"items": [{"id", "title", "title_lang", "description", "starts_at", "ends_at",
                "price_kzt", "organizer", "category", "lat", "lon",
                "place": {"id", "name"} | null, "is_ad": bool,
                "ad_label": "Реклама" | "Ad" | null}]}

Whenever `is_ad` is true the app must show `ad_label` next to the event (SSOT §5.1, §12).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, Request

from app.errors import AppError
from app.events import service
from app.events.schemas import EventList
from app.i18n import pick_locale
from app.live import clock
from app.places import service as places

router = APIRouter(prefix="/v1", tags=["events"])


@router.get("/events", response_model=EventList)
async def list_events(
    request: Request,
    from_: Optional[date] = Query(None, alias="from"),  # noqa: B008
    to: Optional[date] = Query(None),  # noqa: B008
    bbox: Optional[str] = Query(None, description="west,south,east,north"),
    limit: int = Query(service.DEFAULT_LIMIT, ge=1, le=service.MAX_LIMIT),
):
    locale = pick_locale(request.headers.get("accept-language"))
    start = from_ or clock.local_today()
    try:
        end = service.window_end(start, to)
    except ValueError as exc:
        raise AppError(422, "validation_error", str(exc)) from None
    box = None
    if bbox is not None:
        try:
            box = places.parse_bbox(bbox)
        except ValueError as exc:
            raise AppError(422, "validation_error", "Invalid bbox: %s" % exc) from None
    async with request.app.state.db.transaction() as conn:
        rows = await service.load_events(conn, start, end, box, limit)
    return {"items": [service.event_json(r, locale) for r in rows]}
