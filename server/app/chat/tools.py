"""Model tools shared by guest and registered chat: specs, args, place search."""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.chat.brief import BriefUpdate
from app.db import fetch_all
from app.events import service as events_service
from app.live import clock
from app.places import dishes, service, sql
from app.planner import candidates, outside
from app.planner.events import trip_events
from app.providers.llm import ToolSpec
from app.regions import default_region

SEARCH_PLACES = "search_places"
UPDATE_TRIP_BRIEF = "update_trip_brief"
ADD_GRAPH_NODE = "add_graph_node"
BUILD_TRIP = "build_trip"
SEARCH_EVENTS = "search_events"

MAX_SEARCH_LIMIT = 10
MAX_NODE_CHARS = 80
NEAR_RADIUS_M = 3000
DISH_NOTE = (
    "matched by the cuisine of the dish: say these places 'most likely serve' it (cuisine/"
    "category), unless a place has match 'menu' (its menu lists the dish) or 'name'"
)
NEAR_NOT_FOUND_NOTE = "could not locate the `near` place: results are not limited to its area"
OUTSIDE_NOTE = "a place Jol has no data for yet: it cannot be planned in this version"


class SearchPlacesArgs(BaseModel):
    query: Optional[str] = Field(None, max_length=100, description="Part of a place name")
    category: Optional[str] = Field(None, max_length=64, description="Category slug")
    near: Optional[str] = Field(
        None,
        max_length=100,
        description="Name of a place or landmark the results must be close to (about 3 km)",
    )
    limit: int = Field(5, ge=1, le=MAX_SEARCH_LIMIT)
    show_on_map: bool = Field(
        False, description="Registered chat only: pin the results on the user's map as chosen"
    )


class SearchEventsArgs(BaseModel):
    from_date: Optional[date] = Field(
        None, description="First day, YYYY-MM-DD; default: the trip's first day, else today"
    )
    to_date: Optional[date] = Field(
        None, description="Last day, YYYY-MM-DD; default: the trip's last day, else 14 days on"
    )
    limit: int = Field(8, ge=1, le=MAX_SEARCH_LIMIT)


class AddGraphNodeArgs(BaseModel):
    text: str = Field(
        min_length=1, max_length=MAX_NODE_CHARS, description="2-5 word summary of a fact"
    )


class NoArgs(BaseModel):
    pass


SEARCH_PLACES_SPEC = ToolSpec.from_model(
    SEARCH_PLACES,
    "Search the places database of the trip region by name part and/or category. The query may "
    "also be a dish (beshbarmak, plov, sushi, dim sum...): the search then returns places of "
    "the matching cuisine and says which cuisine it matched. `near` limits the results to a "
    "place or landmark's area. Use it to answer "
    "questions about real places; never invent places, prices or hours. Places anywhere in "
    "Kazakhstan come back as places (a far one also has a far block); a well-known place Jol has "
    "no data for comes back as outside_area instead.",
    SearchPlacesArgs,
)
SEARCH_EVENTS_SPEC = ToolSpec.from_model(
    SEARCH_EVENTS,
    "List events (concerts, festivals, exhibitions) in the trip region on given days. "
    "Offer them only when "
    "they fit what the person likes. An event with is_ad true is an advertisement: say so when "
    "you mention it using its ad_label.",
    SearchEventsArgs,
)
UPDATE_TRIP_BRIEF_SPEC = ToolSpec.from_model(
    UPDATE_TRIP_BRIEF,
    "Record trip facts the person stated. Send only new or changed fields. Budget is for the "
    "whole trip in tenge. Lists are added to what is stored.",
    BriefUpdate,
)
ADD_GRAPH_NODE_SPEC = ToolSpec.from_model(
    ADD_GRAPH_NODE, "Add a very short summary of a new fact to the chat graph.", AddGraphNodeArgs
)
BUILD_TRIP_SPEC = ToolSpec.from_model(
    BUILD_TRIP,
    "Build the route once dates, budget and lodging are known and the person is ready.",
    NoArgs,
)


def place_pin(row: Dict[str, Any], locale: str) -> Dict[str, Any]:
    name, _ = service.pick_text(row, "name", locale)
    return {
        "id": str(row["id"]),
        "name": name or "",
        "category": row["category"],
        "lat": row["lat"],
        "lon": row["lon"],
    }


async def search_places(
    db, args: SearchPlacesArgs, locale: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run the places search. Returns (result for the model, pins for the map).

    Read-only (a SELECT in its own transaction), so it is also used by the guest chat.
    """
    query = " ".join((args.query or "").split())
    category = (args.category or "").strip() or None
    if len(query) < 2 and not category:
        return {"error": "give a query of at least 2 characters or a category"}, []
    far = None if category else outside.outside_wish(query)
    if far is not None:
        async with db.transaction() as conn:
            known = await candidates.far_place(conn, query, far)
        if known is None:  # Ш-56: a known place the database has no data for: say so honestly
            return {"places": [], "outside_area": far.as_json(locale), "note": OUTSIDE_NOTE}, []
        # Ш-62: a place of the country the planner can plan (Charyn, Kolsai, Turkistan...)
        row = {
            "id": known.id,
            "name_ru": known.name_ru,
            "name_en": known.name_en,
            "name_kk": None,
            "category": known.category,
            "lat": known.lat,
            "lon": known.lon,
        }
        pin = place_pin(row, locale)
        found = dict(pin, kind=known.kind, popularity=known.popularity, is_partner=False)
        return {"places": [found], "far": far.as_json(locale)}, [pin]
    near_point, near_missing = None, False
    near_name = " ".join((args.near or "").split())
    if len(near_name) >= 2:
        near_point = await _locate(db, near_name)
        near_missing = near_point is None
    if query and not category:
        async with db.transaction() as conn:
            dish = await dishes.resolve(conn, query)
            dish_rows = (
                await dishes.search(conn, dish, args.limit, near_point, NEAR_RADIUS_M)
                if dish
                else []
            )
        if dish_rows:
            return _dish_result(dish, dish_rows, locale, near_point, near_missing)
    params = {
        "bbox": False,
        "west": None,
        "south": None,
        "east": None,
        "north": None,
        "category": category,
        "q": query or None,
        "pattern": service.like_pattern(query) if query else None,
        "near_lat": near_point["lat"] if near_point else None,
        "near_lon": near_point["lon"] if near_point else None,
        "radius_m": NEAR_RADIUS_M,
        "limit": args.limit,
    }
    async with db.transaction() as conn:
        rows = await fetch_all(conn, sql.PLACES_SEARCH, params)
    pins = [place_pin(row, locale) for row in rows]
    found = [
        dict(pin, kind=row["kind"], popularity=row["popularity"], is_partner=row["is_partner"])
        for pin, row in zip(pins, rows)
    ]
    if not found:
        result = {"places": [], "note": "nothing found"}
        if near_missing:
            result["near_not_found"] = True
        return result, []
    return {"places": found, **({"note": NEAR_NOT_FOUND_NOTE} if near_missing else {})}, pins


async def _locate(db, name: str) -> Optional[Dict[str, float]]:
    """Coordinates of the best place by this name (a landmark to search near), or None."""
    params = {
        "bbox": False,
        "west": None,
        "south": None,
        "east": None,
        "north": None,
        "category": None,
        "q": name,
        "pattern": service.like_pattern(name),
        "near_lat": None,
        "near_lon": None,
        "radius_m": NEAR_RADIUS_M,
        "limit": 1,
    }
    async with db.transaction() as conn:
        rows = await fetch_all(conn, sql.PLACES_SEARCH, params)
    return {"lat": rows[0]["lat"], "lon": rows[0]["lon"]} if rows else None


def _dish_result(
    dish: Dict[str, Any],
    rows: List[Dict[str, Any]],
    locale: str,
    near_point: Optional[Dict[str, float]],
    near_missing: bool,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    pins = [place_pin(row, locale) for row in rows]
    found = []
    for pin, row in zip(pins, rows):
        item = dict(
            pin,
            kind=row["kind"],
            popularity=row["popularity"],
            is_partner=row["is_partner"],
            match=dishes.MATCH_NAMES[row["tier"]],
        )
        if row["distance_m"] is not None:
            item["distance_m"] = int(row["distance_m"])
        found.append(item)
    result: Dict[str, Any] = {
        "places": found,
        "matched": {
            "dish": dish["name_ru"] if locale == "ru" else dish["name_en"],
            "cuisines": list(dish["cuisines"]),
        },
        "note": DISH_NOTE,
    }
    if near_missing:
        result["near_not_found"] = True
        result["note"] += "; " + NEAR_NOT_FOUND_NOTE
    return result, pins


def event_for_model(item: Dict[str, Any]) -> Dict[str, Any]:
    """Compact event for the model; `is_ad` must be passed on to the person."""
    return {
        "id": item["id"],
        "title": item["title"],
        "category": item["category"],
        "starts_at": item["starts_at"],
        "ends_at": item["ends_at"],
        "price_kzt": item["price_kzt"],
        "place": item["place"]["name"] if item["place"] else None,
        "lat": item["lat"],
        "lon": item["lon"],
        "organizer": item["organizer"],
        "is_ad": item["is_ad"],
        "ad_label": item["ad_label"],
    }


async def search_events(
    db,
    args: SearchEventsArgs,
    locale: str,
    default_from: Optional[date] = None,
    default_to: Optional[date] = None,
    trip_pace: Optional[str] = None,
) -> Dict[str, Any]:
    """Events in a window, for the model. The window defaults to the trip's dates (registered
    chat) or to the next two weeks. Read-only, so the guest chat uses it too."""
    start = args.from_date or default_from or clock.local_today()
    try:
        end = events_service.window_end(start, args.to_date or default_to)
    except ValueError as exc:
        return {"error": str(exc)}
    async with db.transaction() as conn:
        if default_from:
            rows = await trip_events(conn, start, end, trip_pace, limit=args.limit)
        else:
            rows = await events_service.load_events(
                conn, start, end, default_region().bbox, limit=args.limit
            )
    items = [events_service.event_json(r, locale) for r in rows]
    if not items:
        return {"events": [], "note": "no events on those days"}
    return {"events": [event_for_model(i) for i in items]}
