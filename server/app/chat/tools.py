"""Model tools shared by guest and registered chat: specs, args, place search."""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.chat.brief import BriefUpdate
from app.db import fetch_all
from app.places import service, sql
from app.providers.llm import ToolSpec

SEARCH_PLACES = "search_places"
UPDATE_TRIP_BRIEF = "update_trip_brief"
ADD_GRAPH_NODE = "add_graph_node"
BUILD_TRIP = "build_trip"

MAX_SEARCH_LIMIT = 10
MAX_NODE_CHARS = 80


class SearchPlacesArgs(BaseModel):
    query: Optional[str] = Field(None, max_length=100, description="Part of a place name")
    category: Optional[str] = Field(None, max_length=64, description="Category slug")
    limit: int = Field(5, ge=1, le=MAX_SEARCH_LIMIT)
    show_on_map: bool = Field(
        False, description="Registered chat only: pin the results on the user's map as chosen"
    )


class AddGraphNodeArgs(BaseModel):
    text: str = Field(
        min_length=1, max_length=MAX_NODE_CHARS, description="2-5 word summary of a fact"
    )


class NoArgs(BaseModel):
    pass


SEARCH_PLACES_SPEC = ToolSpec.from_model(
    SEARCH_PLACES,
    "Search the places database of Almaty by name part and/or category. Use it to answer "
    "questions about real places; never invent places, prices or hours.",
    SearchPlacesArgs,
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
    params = {
        "bbox": False,
        "west": None,
        "south": None,
        "east": None,
        "north": None,
        "category": category,
        "q": query or None,
        "pattern": service.like_pattern(query) if query else None,
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
        return {"places": [], "note": "nothing found"}, []
    return {"places": found}, pins
