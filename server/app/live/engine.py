"""The weather re-check engine (Ш-40): which stop suffers, what to propose. Read-only.

`plan_proposal` looks at ONE trip WITHOUT locking it (routing is slow: the caller applies the
result under the lock only if the trip version is unchanged) and returns a `Plan` with at most
one proposal (`Spec`):
1. Pending proposals of an older plan version are to expire. A pending proposal of the current
   version whose problem has gone with the new forecast is to expire too; one that still holds
   blocks new proposals (no nagging; the next one comes after a decision).
2. Suffering stops: an outdoor `activity` from today on, not over yet, in the forecast's reach,
   that `rules.stop_problem` flags. Thunderstorms first, then the earliest day and order. A stop
   that already had a proposal for that day (any answer) is skipped.
3. For the first such stop: (a) move it to the END of another day of the trip (nearest day first,
   never today) where both re-timed days fit, the stop has no problem there and the number of
   suffering stops in the two days drops; else (b) for a stop that is not a must-have, replace
   it with the first nearby indoor activity that fits its day. Must-haves are never swapped for
   another place (SSOT §4) but may change day.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.db import fetch_all
from app.live import rules
from app.live import store as live_store
from app.planner import sql as planner_sql
from app.planner.model import Place, place_from_row
from app.providers.weather.base import ForecastView
from app.routing.service import ALMATY_TZ
from app.trips import edit, store

log = logging.getLogger("app.live")

INDOOR_RADIUS_M = 8000
INDOOR_POOL = 20


@dataclass
class Spec:
    kind: str  # move_day | replace
    item: dict
    place: Place
    day: date
    problem: rules.Problem
    to_day: Optional[date] = None
    target: Optional[Place] = None


def _minutes(moment: datetime) -> int:
    local = moment.astimezone(ALMATY_TZ)
    return local.hour * 60 + local.minute


def outdoor(place: Place) -> bool:
    return place.outdoor or place.setting == "outdoor"


def _problem(forecast: ForecastView, day: date, start: datetime, end: datetime):
    hours = forecast.hours(day)
    if not hours:
        return None
    return rules.stop_problem(hours, _minutes(start), _minutes(end))


def _count(forecast: ForecastView, stops: List[Tuple[Place, date, datetime, datetime, str]]) -> int:
    return sum(
        1
        for place, day, start, end, kind in stops
        if kind == "activity" and outdoor(place) and _problem(forecast, day, start, end)
    )


def _count_rows(forecast: ForecastView, rows: List[dict], places: Dict[UUID, Place]) -> int:
    return _count(
        forecast,
        [(places[r["place_id"]], r["day"], r["starts_at"], r["ends_at"], r["kind"]) for r in rows],
    )


def _count_plan(forecast: ForecastView, day: date, result: Any) -> int:
    return _count(forecast, [(s.place, day, s.start, s.end, s.kind) for s in result.plan.stops])


@dataclass
class Plan:
    """What a re-check decided; applied by the caller under the trip lock (`jobs`).

    `version` is the plan version it was computed for: the caller applies it only while the
    locked trip still has this version. `expire` are pending proposals to close first."""

    version: int
    expire: List[UUID]
    spec: Optional[Spec] = None


async def plan_proposal(
    conn, router: Any, trip: dict, forecast: ForecastView, now: datetime
) -> Plan:
    """Read-only: no writes, no trip lock. Routing may happen here, never under the lock."""
    trip_id = trip["id"]
    items = await store.main_items(conn, trip_id)
    places = await edit._places(conn, sorted({r["place_id"] for r in items}, key=str))
    today = now.astimezone(ALMATY_TZ).date()
    plan = Plan(version=trip["version"], expire=[])

    def problem_of(row: dict) -> Optional[rules.Problem]:
        place = places[row["place_id"]]
        if row["kind"] != "activity" or not outdoor(place):
            return None
        if row["day"] < today or row["ends_at"] <= now:
            return None
        return _problem(forecast, row["day"], row["starts_at"], row["ends_at"])

    for old in await live_store.pending(conn, trip_id):
        if old["trip_version"] != trip["version"]:
            plan.expire.append(old["id"])  # of an older plan version
            continue
        row = next(
            (r for r in items if r["place_id"] == old["place_id"] and r["day"] == old["day"]), None
        )
        if row is not None and problem_of(row) is not None:
            return plan  # still valid and unanswered: wait for the person (spec stays None)
        plan.expire.append(old["id"])

    suffering = [(r, p) for r in items if (p := problem_of(r)) is not None]
    suffering.sort(key=lambda rp: (rp[1].kind != "thunderstorm", rp[0]["day"], rp[0]["ord"]))
    for row, problem in suffering:
        if await live_store.already_proposed(
            conn, trip_id, row["place_id"], row["day"], ignore=plan.expire
        ):
            continue
        spec = await _option(conn, router, trip, forecast, items, places, row, problem, today)
        if spec is not None:
            plan.spec = spec
            return plan
        log.info("no weather alternative for a stop", extra={"trip_id": str(trip_id)})
    return plan


async def _option(
    conn, router, trip, forecast, items, places, row, problem, today
) -> Optional[Spec]:
    place = places[row["place_id"]]
    day = row["day"]
    span = (trip["end_date"] - trip["start_date"]).days
    days = [trip["start_date"] + timedelta(days=i) for i in range(span + 1)]
    others = sorted(
        (d for d in days if d != day and d > today), key=lambda d: (abs((d - day).days), d)
    )
    for to_day in others:
        if not forecast.hours(to_day):
            continue
        before = _count_rows(forecast, [r for r in items if r["day"] in (day, to_day)], places)
        result_from, result_to = await edit.plan_move(
            conn, router, trip, items, row, to_day, forecast
        )
        if not edit.move_fits(row, result_from, result_to):
            continue
        after = _count_plan(forecast, day, result_from) + _count_plan(forecast, to_day, result_to)
        moved = next(s for s in result_to.plan.stops if s.place.id == place.id)
        if after < before and _problem(forecast, to_day, moved.start, moved.end) is None:
            return Spec("move_day", row, place, day, problem, to_day=to_day)
    if not row["is_must_have"]:
        rows = [r for r in items if r["day"] == day]
        taken = [r["place_id"] for r in items]
        found = await fetch_all(
            conn,
            planner_sql.INDOOR_NEAR,
            dict(lat=place.lat, lon=place.lon, radius_m=INDOOR_RADIUS_M, taken=taken,
                 limit=INDOOR_POOL),
        )  # fmt: skip
        candidates = [place_from_row(r) for r in found]
        fit = await edit.first_fit_replacement(
            conn, router, trip, items, row, rows, places, candidates, forecast
        )
        if fit is not None:
            target, result = fit
            return Spec("replace", row, place, day, problem, target=target)
    return None
