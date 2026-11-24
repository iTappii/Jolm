"""Live route of a chat (Ш-54, SSOT §11.1): stops and legs drawn on the map while chatting.

For every must-have wish of the brief that finds a place there is one stop (the best match);
the next best matches (up to 2 more) are its alternatives. Stops follow the order of the wishes;
`ord` is the 1-based position among the stops and is renumbered when a wish is removed. Between
consecutive stops there is a leg from the router: on foot when it takes at most 20 minutes, else
public transport if the network offers it, else by car. The object is always sent whole:

    {"stops": [{"ord", "wish", "place": {id, name, category, lat, lon},
                "alternatives": [{id, name, category, lat, lon}]}],
     "legs":  [{"from_ord", "to_ord", "mode": "walk"|"transit"|"car", "duration_s", "distance_m"}]}

Ш-62 (SSOT §5.4 п. 7): when two consecutive stops are far apart (`intercity_settings`
`min_distance_km` and more) the leg comes from the intercity service instead (`planner.country`
rules: from `country_planner_settings.transfer_min_km` a transfer between cities by plane / train /
bus, the fastest one the budget allows; nearer an outing by road). Such a leg is
`{"mode": "plane"|"train"|"bus_intercity"|"car"|"tour", "duration_s", "distance_m",
"intercity": true, "price_kzt_min"?: int, "price_kzt_max"?: int}`; `duration_s` is door to door with
the hub buffer, the price is per person (per vehicle for "car"). Ordinary legs have no `intercity`.

A leg whose route could not be computed (routing down, no way found) is left out of `legs`; it is
retried on the next change. Stored in `chat_live_stops` / `chat_live_alternatives` (migration
0028); names are read in the chat's locale when the object is built. The trip generator takes
the chosen stop place for its wish (`chosen_places`).
"""

import asyncio
import logging
import math
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from app.chat import tools
from app.db import execute, fetch_all, fetch_one
from app.live import clock
from app.planner import country as ctry
from app.planner.travel import DirectionsLegs
from app.regions import default_region
from app.routing import RoutingError, RoutingUnavailable, get_network
from app.routing.costs import IntercityParams, Tariff, load_intercity_params, load_tariffs
from app.routing.fake import haversine_m

log = logging.getLogger(__name__)

MAX_PLACES_PER_WISH = 3  # the best one is the stop, the rest are alternatives
WALK_MAX_S = 20 * 60

LOCK_CLASS = 54  # first key of the advisory lock; the second one is the hash of the chat id


class _Locked:
    """`db` stand-in that runs everything on the connection holding the chat lock (savepoints)."""

    def __init__(self, conn) -> None:
        self.conn = conn

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Any]:
        async with self.conn.transaction():
            yield self.conn


@asynccontextmanager
async def chat_lock(db, chat_id: UUID) -> AsyncIterator[_Locked]:
    """Serialise live-route changes of one chat (Ш-63): `choose` and `sync` read the stops,
    ask the router and write them back, so two of them at once would lose one of the changes.

    A transaction-level advisory lock keyed by the chat id (the chat row itself stays free for
    other writers, e.g. messages). Everything inside runs on this one connection, so it is one
    transaction: it commits when the block ends and rolls back if it raises."""
    async with db.transaction() as conn:
        await execute(
            conn, "SELECT pg_advisory_xact_lock(%s, hashtext(%s))", (LOCK_CLASS, str(chat_id))
        )
        yield _Locked(conn)


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
        "SELECT ord, wish, place_id, leg_mode, leg_duration_s, leg_distance_m, leg_intercity, "
        "leg_price_kzt_min, leg_price_kzt_max FROM chat_live_stops WHERE chat_id = %s ORDER BY ord",
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
            if row["leg_intercity"]:  # Ш-62
                stop.leg["intercity"] = True
                for key, column in (("price_kzt_min", "leg_price_kzt_min"),
                                    ("price_kzt_max", "leg_price_kzt_max")):  # fmt: skip
                    if row[column] is not None:
                        stop.leg[key] = row[column]
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
            "leg_duration_s, leg_distance_m, leg_intercity, leg_price_kzt_min, "
            "leg_price_kzt_max) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                chat_id,
                ord_,
                stop.wish,
                stop.place_id,
                leg.get("mode"),
                leg.get("duration_s"),
                leg.get("distance_m"),
                bool(leg.get("intercity")),
                leg.get("price_kzt_min"),
                leg.get("price_kzt_max"),
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


LEG_CONCURRENCY = 4  # routing calls in flight at once while the legs of a route are filled

# intercity.service mode -> the mode of a live-route leg (the contract of the iOS app)
INTERCITY_MODES = {
    "plane": "plane",
    "train": "train",
    "bus": "bus_intercity",
    "car": "car",
    "tour": "tour",
}


@dataclass
class LegContext:
    """What the legs of one route are computed with; read once per pass (Ш-64)."""

    tariffs: Dict[str, Tariff]
    network: Any
    params: Optional[IntercityParams] = None  # Ш-62: None = no intercity data, city legs only
    settings: Optional[ctry.Settings] = None
    budget_kzt: Optional[int] = None  # the brief's budget: a transfer must be affordable
    # far legs read the database on the pass's single connection, one at a time
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def intercity(self) -> bool:
        return self.params is not None and self.settings is not None


def pick_intercity_leg(
    raw: Sequence[Dict[str, Any]],
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    settings: ctry.Settings,
    budget_kzt: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """The live-route leg for two far stops from the options of `intercity.service`.

    Same rule as the trip planner (`planner.country.rank_options`): from `transfer_min_km` a
    transfer between cities (plane / train / bus), the fastest one whose upper price is within
    `transfer_budget_share` of the budget (no budget known: the fastest); nearer an outing by road
    (own car / tour; a taxi is the same road and is not offered here). None when nothing fits."""
    pool = [o for o in raw if o["mode"] in INTERCITY_MODES]
    if not pool:
        return None
    transfer = ctry.km(origin, destination) >= settings.transfer_min_km
    cap = budget_kzt * settings.transfer_budget_share if budget_kzt else math.inf
    chosen = ctry.rank_options(pool, transfer, cap)[0]
    leg: Dict[str, Any] = {
        "mode": INTERCITY_MODES[chosen["mode"]],
        "duration_s": int(round(chosen["duration_s_max"])),
        "distance_m": int(round(chosen.get("distance_m") or haversine_m(origin, destination))),
        "intercity": True,
    }
    for key, source in (("price_kzt_min", "cost_kzt_min"), ("price_kzt_max", "cost_kzt_max")):
        if chosen.get(source) is not None:
            leg[key] = int(chosen[source])
    return leg


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


async def leg_context(db, budget_kzt: Optional[int] = None) -> LegContext:
    """Tariffs, transit network and intercity data the legs of one route are computed with; read
    once, so the legs can then be computed concurrently without touching the database."""
    now: datetime = clock.now()
    async with db.transaction() as conn:
        tariffs = await load_tariffs(conn, now.date())
        network = await get_network(conn) if "bus" in tariffs or "metro" in tariffs else None
        params = await load_intercity_params(conn)
        settings = await ctry.load_settings(conn)
    return LegContext(tariffs, network, params, settings, budget_kzt)


async def _intercity_leg(
    db, router: Any, origin: Tuple[float, float], destination: Tuple[float, float], ctx: LegContext
) -> Optional[Dict[str, Any]]:
    """Ш-62: the leg between far stops, or None when `intercity.service` has nothing for the pair
    (the ordinary city options then decide). Raises RoutingUnavailable when the router is down.

    A pair no hub serves on one side (the Kolsai Lakes to Turkistan: no airport or station within
    reach of the lakes) goes through the home city, as the trip does: the road home, then the
    transfer from there. One leg: the times and prices are added, the mode is the transfer's."""
    from app.intercity.service import intercity_options  # late: it imports the routing service

    assert ctx.params is not None and ctx.settings is not None
    now = clock.now()

    async def options(a, b):
        async with ctx.lock:  # one query at a time on the pass's connection
            async with db.transaction() as conn:
                return await intercity_options(
                    conn, router, ctx.tariffs, ctx.params, a, b, None, "ru", now
                )

    raw = await options(origin, destination)
    direct = pick_intercity_leg(raw, origin, destination, ctx.settings, ctx.budget_kzt)
    if direct is not None:
        return direct
    home = default_region().centre
    if ctry.km(origin, home) <= ctx.settings.local_radius_km:
        return None
    if ctry.km(destination, home) <= ctx.settings.local_radius_km:
        return None  # the road back to the city is a plain road: nothing to compose
    first = pick_intercity_leg(
        await options(origin, home), origin, home, ctx.settings, ctx.budget_kzt
    )
    second = pick_intercity_leg(
        await options(home, destination), home, destination, ctx.settings, ctx.budget_kzt
    )
    if first is None or second is None:
        return None
    leg = {
        "mode": second["mode"],
        "duration_s": first["duration_s"] + second["duration_s"],
        "distance_m": first["distance_m"] + second["distance_m"],
        "intercity": True,
    }
    for key in ("price_kzt_min", "price_kzt_max"):
        if key in first and key in second:
            leg[key] = first[key] + second[key]
    return leg


async def compute_leg(
    db,
    router: Any,
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    context: Optional[LegContext] = None,
) -> Optional[Dict[str, Any]]:
    ctx = context if context is not None else await leg_context(db)
    if ctx.intercity and ctx.params and ctx.params.min_distance_km <= ctry.km(origin, destination):
        try:
            far = await _intercity_leg(db, router, origin, destination, ctx)
        except RoutingUnavailable:
            return None
        if far is not None:
            return far
    legs = DirectionsLegs(router, ctx.network, ctx.tariffs)
    try:
        options = await legs.options(origin, destination, clock.now())
    except RoutingError:
        return None
    return pick_leg(options)


async def _fill_legs(
    db,
    router: Any,
    stops: List[Stop],
    places: Dict[UUID, Dict[str, Any]],
    old: List[Stop],
    budget_kzt: Optional[int] = None,
) -> None:
    """Leg for every stop but the first. A leg is reused when the same pair of places (previous
    place, this place) already had one; otherwise it is computed (Ш-64: the missing ones
    concurrently, at most LEG_CONCURRENCY at a time; same results as one by one)."""
    known: Dict[Tuple[UUID, UUID], Dict[str, Any]] = {}
    for index, stop in enumerate(old):
        if index > 0 and stop.leg:
            known[(old[index - 1].place_id, stop.place_id)] = stop.leg
    missing: List[Tuple[Stop, Tuple[float, float], Tuple[float, float]]] = []
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
            missing.append((stop, (a["lat"], a["lon"]), (b["lat"], b["lon"])))
    if not missing:
        return
    started = time.perf_counter()
    context = await leg_context(db, budget_kzt)
    gate = asyncio.Semaphore(LEG_CONCURRENCY)

    async def one(origin: Tuple[float, float], destination: Tuple[float, float]):
        async with gate:
            return await compute_leg(db, router, origin, destination, context)

    results = await asyncio.gather(*(one(o, d) for _, o, d in missing))
    for (stop, _, _), leg in zip(missing, results):
        stop.leg = leg
    log.info(
        "live route legs",
        extra={"legs": len(missing), "legs_ms": round((time.perf_counter() - started) * 1000)},
    )


async def _budget(db, chat_id: UUID) -> Optional[int]:
    """The trip budget of the chat's brief (a transfer must be affordable), None when not known."""
    async with db.transaction() as conn:
        row = await fetch_one(
            conn, "SELECT budget_kzt FROM trip_briefs WHERE chat_id = %s", (chat_id,)
        )
    return row["budget_kzt"] if row else None


# --- sync with the brief --------------------------------------------------------------------


async def sync(
    db, chat_id: UUID, locale: str, router: Any, wishes: Sequence[str]
) -> Tuple[Optional[Dict[str, Any]], bool, Dict[str, Dict[str, Any]]]:
    """Bring the stops in line with the brief's must-have wishes.

    Returns (live route or None, changed, best pins of the NEW wishes by wish). New wishes are
    searched (up to 3 places); wishes that are gone lose their stop; legs are recomputed where
    the neighbours changed. A wish without any place gets no stop (and is searched again next time).
    """
    async with chat_lock(db, chat_id) as locked:
        return await _sync_locked(locked, chat_id, locale, router, wishes)


async def _sync_locked(
    db, chat_id: UUID, locale: str, router: Any, wishes: Sequence[str]
) -> Tuple[Optional[Dict[str, Any]], bool, Dict[str, Dict[str, Any]]]:
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
    await _fill_legs(db, router, stops, places, old, await _budget(db, chat_id))
    async with db.transaction() as conn:
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
    Serialised per chat (`chat_lock`): the stops are read under the lock, so a concurrent choose or
    sync is never overwritten.
    """
    async with chat_lock(db, chat_id) as locked:
        return await _choose_locked(locked, chat_id, locale, router, ord_, place_id)


async def _choose_locked(
    db, chat_id: UUID, locale: str, router: Any, ord_: int, place_id: UUID
) -> Dict[str, Any]:
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
        await _fill_legs(db, router, stops, places, old, await _budget(db, chat_id))
        async with db.transaction() as conn:
            await _save_stops(conn, chat_id, stops)
    result = await _render(db, chat_id, stops, locale)
    assert result is not None
    return result
