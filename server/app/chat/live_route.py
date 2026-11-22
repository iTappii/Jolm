"""Live route of a chat (Ш-54, SSOT §11.1): stops and legs drawn on the map while chatting.

For every must-have wish of the brief that finds a place there is one stop (the best match);
the next best matches (up to 2 more) are its alternatives. Stops follow the order of the wishes;
`ord` is the 1-based position among the stops and is renumbered when a wish is removed. Between
consecutive stops there is a leg from the router: on foot when it takes at most 20 minutes, else
public transport if the network offers it, else by car. The object is always sent whole:

    {"stops": [{"ord", "wish", "place": {id, name, category, lat, lon},
                "alternatives": [{id, name, category, lat, lon}]}],
     "legs":  [{"from_ord", "to_ord", "mode": "walk"|"transit"|"car", "duration_s", "distance_m"}]}

A leg whose route could not be computed (routing down, no way found) is left out of `legs`; it is
retried on the next change. Stored in `chat_live_stops` / `chat_live_alternatives` (migration
0028); names are read in the chat's locale when the object is built. The trip generator takes
the chosen stop place for its wish (`chosen_places`).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from app.chat import tools
from app.db import execute, fetch_all, fetch_one
from app.live import clock
from app.planner.travel import DirectionsLegs
from app.routing import RoutingError, get_network
from app.routing.costs import load_tariffs

MAX_PLACES_PER_WISH = 3  # the best one is the stop, the rest are alternatives
WALK_MAX_S = 20 * 60

PLACES_BY_ID = """
SELECT p.id, p.name_ru, p.name_en, p.name_kk, c.slug AS category,
       ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon
FROM places p LEFT JOIN place_categories c ON c.id = p.category_id
WHERE p.id = ANY(%s)
"""


class Stop:
    def __init__(self, wish: str, place_id: UUID, alternatives: List[UUID]) -> None:
        self.wish = wish
        self.place_id = place_id
        self.alternatives = alternatives
        self.leg: Optional[Dict[str, Any]] = None  # leg from the previous stop


async def _load_stops(conn, chat_id: UUID) -> List[Stop]:
    rows = await fetch_all(
        conn,
        "SELECT ord, wish, place_id, leg_mode, leg_duration_s, leg_distance_m "
        "FROM chat_live_stops WHERE chat_id = %s ORDER BY ord",
        (chat_id,),
    )
    alts = await fetch_all(
        conn,
        "SELECT ord, place_id FROM chat_live_alternatives WHERE chat_id = %s ORDER BY ord, rank",
        (chat_id,),
    )
    by_ord: Dict[int, List[UUID]] = {}
    for row in alts:
        by_ord.setdefault(row["ord"], []).append(row["place_id"])
    stops = []
    for row in rows:
        stop = Stop(row["wish"], row["place_id"], by_ord.get(row["ord"], []))
        if row["leg_mode"]:
            stop.leg = {
                "mode": row["leg_mode"],
                "duration_s": row["leg_duration_s"],
                "distance_m": row["leg_distance_m"],
            }
        stops.append(stop)
    return stops


async def _save_stops(conn, chat_id: UUID, stops: Sequence[Stop]) -> None:
    await execute(conn, "DELETE FROM chat_live_alternatives WHERE chat_id = %s", (chat_id,))
    await execute(conn, "DELETE FROM chat_live_stops WHERE chat_id = %s", (chat_id,))
    for ord_, stop in enumerate(stops, 1):
        leg = stop.leg or {}
        await execute(
            conn,
            "INSERT INTO chat_live_stops (chat_id, ord, wish, place_id, leg_mode, "
            "leg_duration_s, leg_distance_m) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                chat_id,
                ord_,
                stop.wish,
                stop.place_id,
                leg.get("mode"),
                leg.get("duration_s"),
                leg.get("distance_m"),
            ),
        )
        for rank, alt in enumerate(stop.alternatives):
            await execute(
                conn,
                "INSERT INTO chat_live_alternatives (chat_id, ord, place_id, rank) "
                "VALUES (%s, %s, %s, %s)",
                (chat_id, ord_, alt, rank),
            )


async def _places(conn, ids: Sequence[UUID]) -> Dict[UUID, Dict[str, Any]]:
    rows = await fetch_all(conn, PLACES_BY_ID, (list(ids),)) if ids else []
    return {row["id"]: row for row in rows}


def render(
    stops: Sequence[Stop], places: Dict[UUID, Dict[str, Any]], locale: str
) -> Dict[str, Any]:
    """The public object; a stop whose place no longer exists is skipped (cannot be drawn)."""
    out_stops: List[Dict[str, Any]] = []
    legs: List[Dict[str, Any]] = []
    previous_ord: Optional[int] = None
    for stop in stops:
        row = places.get(stop.place_id)
        if row is None:
            continue
        ord_ = len(out_stops) + 1
        out_stops.append(
            {
                "ord": ord_,
                "wish": stop.wish,
                "place": tools.place_pin(row, locale),
                "alternatives": [
                    tools.place_pin(places[a], locale) for a in stop.alternatives if a in places
                ],
            }
        )
        if previous_ord is not None and stop.leg:
            legs.append(dict(from_ord=previous_ord, to_ord=ord_, **stop.leg))
        previous_ord = ord_
    return {"stops": out_stops, "legs": legs}


async def load(conn, chat_id: UUID, locale: str) -> Optional[Dict[str, Any]]:
    """The stored live route, or None when the chat has no stops."""
    stops = await _load_stops(conn, chat_id)
    if not stops:
        return None
    ids = [s.place_id for s in stops] + [a for s in stops for a in s.alternatives]
    return render(stops, await _places(conn, ids), locale)


async def chosen_places(conn, chat_id: UUID) -> Dict[str, UUID]:
    """wish (case-folded) -> the place of its stop; the trip generator uses these (Ш-54)."""
    rows = await fetch_all(
        conn, "SELECT wish, place_id FROM chat_live_stops WHERE chat_id = %s", (chat_id,)
    )
    return {row["wish"].casefold(): row["place_id"] for row in rows}


# --- legs ------------------------------------------------------------------------------------


def pick_leg(options: Sequence[Any]) -> Optional[Dict[str, Any]]:
    """Walk if it takes at most 20 minutes, else transit if offered, else car/taxi."""

    def best(group: Tuple[str, ...]) -> Optional[Any]:
        found = [o for o in options if o.group in group]
        return min(found, key=lambda o: o.duration_s) if found else None

    walk, transit, car = best(("walk",)), best(("transit",)), best(("car", "taxi"))
    if walk is not None and walk.duration_s <= WALK_MAX_S:
        chosen, mode = walk, "walk"
    elif transit is not None:
        chosen, mode = transit, "transit"
    elif car is not None:
        chosen, mode = car, "car"
    elif walk is not None:  # nothing else exists: a long walk is still a way
        chosen, mode = walk, "walk"
    else:
        return None
    return {
        "mode": mode,
        "duration_s": int(round(chosen.duration_s)),
        "distance_m": int(round(chosen.distance_m)),
    }


async def compute_leg(
    db, router: Any, origin: Tuple[float, float], destination: Tuple[float, float]
) -> Optional[Dict[str, Any]]:
    now: datetime = clock.now()
    async with db.transaction() as conn:
        tariffs = await load_tariffs(conn, now.date())
        network = await get_network(conn) if "bus" in tariffs or "metro" in tariffs else None
    legs = DirectionsLegs(router, network, tariffs)
    try:
        options = await legs.options(origin, destination, now)
    except RoutingError:
        return None
    return pick_leg(options)


async def _fill_legs(
    db, router: Any, stops: List[Stop], places: Dict[UUID, Dict[str, Any]], old: List[Stop]
) -> None:
    """Leg for every stop but the first. A leg is reused when the same pair of places (previous
    place, this place) already had one; otherwise it is computed."""
    known: Dict[Tuple[UUID, UUID], Dict[str, Any]] = {}
    for index, stop in enumerate(old):
        if index > 0 and stop.leg:
            known[(old[index - 1].place_id, stop.place_id)] = stop.leg
    for index, stop in enumerate(stops):
        stop.leg = None
        if index == 0:
            continue
        previous = stops[index - 1]
        cached = known.get((previous.place_id, stop.place_id))
        if cached:
            stop.leg = cached
            continue
        a, b = places.get(previous.place_id), places.get(stop.place_id)
        if a is not None and b is not None:
            stop.leg = await compute_leg(db, router, (a["lat"], a["lon"]), (b["lat"], b["lon"]))


# --- sync with the brief --------------------------------------------------------------------


async def sync(
    db, chat_id: UUID, locale: str, router: Any, wishes: Sequence[str]
) -> Tuple[Optional[Dict[str, Any]], bool, Dict[str, Dict[str, Any]]]:
    """Bring the stops in line with the brief's must-have wishes.

    Returns (live route or None, changed, best pins of the NEW wishes by wish). New wishes are
    searched (up to 3 places); wishes that are gone lose their stop; legs are recomputed where
    the neighbours changed. A wish without any place gets no stop (and is searched again next time).
    """
    async with db.transaction() as conn:
        old = await _load_stops(conn, chat_id)
    by_wish = {stop.wish.casefold(): stop for stop in old}
    taken = {stop.place_id for stop in old}
    new_pins: Dict[str, Dict[str, Any]] = {}
    stops: List[Stop] = []
    for wish in wishes:
        key = wish.casefold()
        if key in by_wish:
            stops.append(by_wish[key])
            continue
        found = await _search(db, wish, locale, taken)
        if not found:
            continue
        pins, ids = found
        new_pins[wish] = pins[0]
        taken.add(ids[0])
        stops.append(Stop(wish, ids[0], ids[1:]))

    def shape(items: Sequence[Stop]) -> List[Any]:
        return [(s.wish, s.place_id, tuple(sorted((s.leg or {}).items()))) for s in items]

    before = shape(old)
    same = [x[:2] for x in before] == [x[:2] for x in shape(stops)]
    if same and all(i == 0 or s.leg for i, s in enumerate(stops)):
        return (await _render(db, chat_id, stops, locale), False, new_pins)
    async with db.transaction() as conn:
        ids = [s.place_id for s in stops] + [a for s in stops for a in s.alternatives]
        places = await _places(conn, ids)
    await _fill_legs(db, router, stops, places, old)
    async with db.transaction() as conn:
        await fetch_one(conn, "SELECT id FROM chats WHERE id = %s FOR UPDATE", (chat_id,))
        await _save_stops(conn, chat_id, stops)
    changed = shape(stops) != before
    return render(stops, places, locale) if stops else None, changed, new_pins


async def _render(db, chat_id: UUID, stops: List[Stop], locale: str) -> Optional[Dict[str, Any]]:
    if not stops:
        return None
    async with db.transaction() as conn:
        ids = [s.place_id for s in stops] + [a for s in stops for a in s.alternatives]
        return render(stops, await _places(conn, ids), locale)


async def _search(
    db, wish: str, locale: str, taken: set
) -> Optional[Tuple[List[Dict[str, Any]], List[UUID]]]:
    """Up to 3 places for a wish (best first), preferring places no other stop uses."""
    limit = min(MAX_PLACES_PER_WISH + len(taken), tools.MAX_SEARCH_LIMIT)
    _, pins = await tools.search_places(db, tools.SearchPlacesArgs(query=wish, limit=limit), locale)
    if not pins:
        return None
    fresh = [p for p in pins if UUID(p["id"]) not in taken]
    chosen = (fresh or pins)[:MAX_PLACES_PER_WISH]
    return chosen, [UUID(p["id"]) for p in chosen]


# --- choose ------------------------------------------------------------------------------------


class ChoiceError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


async def choose(
    db, chat_id: UUID, locale: str, router: Any, ord_: int, place_id: UUID
) -> Dict[str, Any]:
    """Make an alternative the stop at `ord_` (the old stop place becomes an alternative).

    404 no such stop; 422 the place is neither the stop nor one of its alternatives.
    """
    async with db.transaction() as conn:
        old = await _load_stops(conn, chat_id)
    if not 1 <= ord_ <= len(old):
        raise ChoiceError(404, "not_found")
    stop = old[ord_ - 1]
    if place_id != stop.place_id and place_id not in stop.alternatives:
        raise ChoiceError(422, "validation_error")
    stops = [Stop(s.wish, s.place_id, list(s.alternatives)) for s in old]
    for new, was in zip(stops, old):
        new.leg = was.leg
    target = stops[ord_ - 1]
    if place_id != target.place_id:
        target.alternatives = [a for a in target.alternatives if a != place_id] + [target.place_id]
        target.place_id = place_id
        async with db.transaction() as conn:
            ids = [s.place_id for s in stops] + [a for s in stops for a in s.alternatives]
            places = await _places(conn, ids)
        await _fill_legs(db, router, stops, places, old)
        async with db.transaction() as conn:
            await fetch_one(conn, "SELECT id FROM chats WHERE id = %s FOR UPDATE", (chat_id,))
            await _save_stops(conn, chat_id, stops)
    result = await _render(db, chat_id, stops, locale)
    assert result is not None
    return result
