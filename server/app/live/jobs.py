"""Live-plan jobs (Ш-40), run by the worker queue.

    weather.scan   (every hour)   trips due for a re-check -> `weather.recheck` jobs
    weather.recheck {trip_id}      forecast -> at most one proposal (+ chat message + push job)
    mountain.scan  (every 15 min)  from 07:00 Almaty: today's mountain stops -> `mountain.notify`
    mountain.notify {trip_id, day} fresh forecast at the place -> chat message + push job
    push.send {notification_id}    deliver the outbox row to the user's devices

Re-check cadence: a trip is due when `weather_checked_at` is empty or at least RECHECK_INTERVAL
(2 days) old; it is stamped on every finished re-check and when the plan is built. Active =
status 'active' and not ended (`end_date >= today` in Almaty). Mountains: MOUNTAIN_NOTIFY_AT
(07:00) is the earliest local time of the message, and it is sent only while the day's first
mountain stop is still ahead. All times come from `live.clock` (a fake clock in tests).
Idempotency: `trip_day_notices` (one mountain message per trip day), `push_notifications.dedupe_key`
and per-device `delivered_to`.
"""

import logging
from datetime import date, time, timedelta
from typing import Any, Dict, List
from uuid import UUID

from app import worker
from app.db import Database, execute, fetch_all, fetch_one
from app.live import clock, deps, engine, messages, proposals, rules
from app.live import store as live_store
from app.planner.area import ALMATY_CENTRE
from app.providers.weather.base import ForecastView, WeatherUnavailable
from app.providers.weather.open_meteo import HORIZON_DAYS
from app.push import PushError, PushMessage
from app.routing.service import ALMATY_TZ
from app.trips import store as trips_store

log = logging.getLogger("app.live")

RECHECK_INTERVAL = timedelta(days=2)
MOUNTAIN_NOTIFY_AT = time(7, 0)  # Asia/Almaty
SCAN_LIMIT = 500
RECHECK_ATTEMPTS = 3  # plan attempts before the job gives up and is retried by the worker


class TripChanged(Exception):
    """The trip kept changing while a re-check was being planned; retry the job later."""


def _days_ahead(today: date, end: date) -> List[date]:
    last = min(end, today + timedelta(days=HORIZON_DAYS - 1))
    return [today + timedelta(days=i) for i in range((last - today).days + 1)]


@worker.register("weather.scan")
async def weather_scan(conn, payload: dict) -> None:
    now = clock.now()
    today = clock.local_today(now)
    rows = await fetch_all(
        conn,
        "SELECT id FROM trips WHERE status = 'active' AND end_date >= %s "
        "AND (weather_checked_at IS NULL OR weather_checked_at <= %s) "
        "ORDER BY weather_checked_at NULLS FIRST, id LIMIT %s",
        (today, now - RECHECK_INTERVAL, SCAN_LIMIT),
    )
    for row in rows:
        await worker.enqueue(
            conn, "weather.recheck", {"trip_id": str(row["id"])},
            dedupe_key="weather.recheck:%s:%s" % (row["id"], today.isoformat()),
        )  # fmt: skip


@worker.register("weather.recheck", external=True)
async def weather_recheck(db: Database, payload: dict) -> None:
    trip_id, force = UUID(payload["trip_id"]), bool(payload.get("force"))
    now = clock.now()
    today = clock.local_today(now)
    async with db.transaction() as conn:
        trip = await fetch_one(
            conn,
            "SELECT id, user_id, status, end_date, weather_checked_at FROM trips WHERE id = %s",
            (trip_id,),
        )
    if trip is None or trip["status"] != "active" or trip["end_date"] < today:
        return
    checked = trip["weather_checked_at"]
    if not force and checked is not None and now - checked < RECHECK_INTERVAL:
        return  # a duplicate job: someone checked recently
    days = _days_ahead(today, trip["end_date"])
    forecast = ForecastView(await deps.weather(db).forecast(*ALMATY_CENTRE, days))  # may raise
    # plan-then-apply: routing runs WITHOUT the trip lock; the result is applied under the lock
    # only if the plan version is unchanged, else it is recomputed (a few times, then the job
    # is retried later by the worker, and `weather_checked_at` stays as it was)
    for _ in range(RECHECK_ATTEMPTS):
        async with db.transaction() as conn:
            current = await trips_store.get_trip_row(conn, trip["user_id"], trip_id)
            if current is None or current["status"] != "active":
                return
            plan = await engine.plan_proposal(conn, deps.router(), current, forecast, now)
        async with db.transaction() as conn:
            locked = await trips_store.get_trip_row(conn, trip["user_id"], trip_id, lock=True)
            if locked is None or locked["status"] != "active":
                return
            if locked["version"] != plan.version:
                continue  # the plan changed while we were routing: recompute
            await _apply(conn, locked, plan, now)
            return
    raise TripChanged("trip %s changed during every re-check attempt" % trip_id)


async def _apply(conn, locked: dict, plan: engine.Plan, now) -> None:
    """Writes only (under the trip lock): close what the plan closes, store the proposal."""
    trip_id = locked["id"]
    await live_store.expire(conn, plan.expire)
    spec = plan.spec
    if spec is not None:
        # proposals decided or created by someone else since the plan was read: do not nag
        if await live_store.pending(conn, trip_id) or await live_store.already_proposed(
            conn, trip_id, spec.place.id, spec.day
        ):
            spec = None
    if spec is not None:
        chat = await live_store.chat_of(conn, locked["chat_id"])
        locale = chat["locale"] if chat else await _user_locale(conn, locked["user_id"])
        await proposals.create(conn, locked, spec, locale, chat["id"] if chat else None)
    await execute(conn, "UPDATE trips SET weather_checked_at = %s WHERE id = %s", (now, trip_id))


async def _user_locale(conn, user_id: UUID) -> str:
    row = await fetch_one(conn, "SELECT locale FROM users WHERE id = %s", (user_id,))
    return row["locale"] if row else "en"


# --- mountains (SSOT §7.2) ------------------------------------------------------------------
@worker.register("mountain.scan")
async def mountain_scan(conn, payload: dict) -> None:
    now = clock.now()
    local = now.astimezone(ALMATY_TZ)
    if local.time() < MOUNTAIN_NOTIFY_AT:
        return
    rows = await fetch_all(
        conn,
        """
        SELECT i.trip_id, i.day FROM trip_items i
        JOIN trips t ON t.id = i.trip_id JOIN places p ON p.id = i.place_id
        WHERE i.variant = 'main' AND i.kind = 'activity' AND p.is_mountain AND i.day = %s
          AND t.status = 'active'
          AND NOT EXISTS (SELECT 1 FROM trip_day_notices n
                          WHERE n.trip_id = i.trip_id AND n.day = i.day AND n.kind = 'mountain')
        GROUP BY i.trip_id, i.day HAVING min(i.starts_at) > %s
        LIMIT %s
        """,
        (local.date(), now, SCAN_LIMIT),
    )
    for row in rows:
        await worker.enqueue(
            conn, "mountain.notify",
            {"trip_id": str(row["trip_id"]), "day": row["day"].isoformat()},
            dedupe_key="mountain:%s:%s" % (row["trip_id"], row["day"].isoformat()),
        )  # fmt: skip


def _stats(hours: List[Any], start: int, end: int) -> Dict[str, Any]:
    known = [hours[h] for h in rules.visit_hours(start, end) if 0 <= h < len(hours) and hours[h]]
    temps = [w.temperature_c for w in known if w.temperature_c is not None]
    rains = [w.rain_probability for w in known if w.rain_probability is not None]
    winds = [w.wind_kmh for w in known if w.wind_kmh is not None]
    return {
        "tmin": min(temps) if temps else None,
        "tmax": max(temps) if temps else None,
        "rain": max(rains) if rains else None,
        "wind": max(winds) if winds else None,
    }


@worker.register("mountain.notify", external=True)
async def mountain_notify(db: Database, payload: dict) -> None:
    trip_id, day = UUID(payload["trip_id"]), date.fromisoformat(payload["day"])
    now = clock.now()
    async with db.transaction() as conn:
        trip = await fetch_one(
            conn, "SELECT id, user_id, chat_id, status FROM trips WHERE id = %s", (trip_id,)
        )
        if trip is None or trip["status"] != "active":
            return
        places = await fetch_all(
            conn,
            """
            SELECT p.id, p.name_ru, p.name_en, p.elevation_m,
                   ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
                   i.starts_at, i.ends_at
            FROM trip_items i JOIN places p ON p.id = i.place_id
            WHERE i.trip_id = %s AND i.variant = 'main' AND i.day = %s AND i.kind = 'activity'
              AND p.is_mountain ORDER BY i.ord
            """,
            (trip_id, day),
        )
        noticed = await fetch_one(
            conn,
            "SELECT 1 AS ok FROM trip_day_notices WHERE trip_id = %s AND day = %s "
            "AND kind = 'mountain'",
            (trip_id, day),
        )
    if noticed or not places or now >= min(p["starts_at"] for p in places):
        return  # done already, nothing planned, or the walk has begun
    forecasts = {}
    for place in places:  # fresh forecast at the place's own point and elevation
        forecasts[place["id"]] = await deps.weather(db).forecast(
            place["lat"], place["lon"], [day], place["elevation_m"]
        )  # WeatherUnavailable propagates: the job is retried
    async with db.transaction() as conn:
        locked = await trips_store.get_trip_row(conn, trip["user_id"], trip_id, lock=True)
        if locked is None:
            return
        if not await live_store.add_notice(conn, trip_id, day, "mountain"):
            return  # another run won
        chat = await live_store.chat_of(conn, trip["chat_id"])
        locale = chat["locale"] if chat else await _user_locale(conn, trip["user_id"])
        rows = []
        for place in places:
            weather = forecasts[place["id"]].get(day)
            hours = list(weather.hours) if weather else []
            start = place["starts_at"].astimezone(ALMATY_TZ)
            end = place["ends_at"].astimezone(ALMATY_TZ)
            s_min, e_min = start.hour * 60 + start.minute, end.hour * 60 + end.minute
            problem = (
                rules.stop_problem(
                    hours, s_min, e_min, rules.MOUNTAIN_WIND_KMH, rules.MOUNTAIN_COLD_C
                )
                if hours
                else None
            )
            name = (
                (place["name_ru"] or place["name_en"] or "")
                if locale == "ru"
                else (place["name_en"] or place["name_ru"] or "")
            )
            rows.append(
                dict(_stats(hours, s_min, e_min), place=name, start=start.strftime("%H:%M"),
                     problem=problem)
            )  # fmt: skip
        if all(r["tmin"] is None for r in rows):
            raise WeatherUnavailable("no forecast for the mountain day")
        texts = messages.mountain_texts(locale, rows)
        if chat:
            await live_store.add_chat_message(
                conn, chat["id"], texts["message"], "system.mountain.v1"
            )
        note = await live_store.add_notification(
            conn, trip["user_id"], "mountain_morning", texts["title"], texts["body"],
            {"type": "mountain_morning", "trip_id": str(trip_id),
             "chat_id": str(chat["id"]) if chat else None},
            "mountain:%s:%s" % (trip_id, day.isoformat()),
        )  # fmt: skip
        if note is not None:
            await worker.enqueue(conn, "push.send", {"notification_id": str(note)})


# --- push -----------------------------------------------------------------------------------
@worker.register("push.send", external=True)
async def push_send(db: Database, payload: dict) -> None:
    nid = UUID(payload["notification_id"])
    async with db.transaction() as conn:
        note = await fetch_one(
            conn,
            "SELECT id, user_id, title, body, data, delivered_to, sent_at "
            "FROM push_notifications WHERE id = %s",
            (nid,),
        )
        if note is None or note["sent_at"] is not None:
            return  # idempotent: already delivered
        devices = await fetch_all(
            conn,
            "SELECT id, apns_token FROM devices WHERE user_id = %s AND apns_token IS NOT NULL "
            "AND NOT (id = ANY(%s)) ORDER BY created_at, id",
            (note["user_id"], note["delivered_to"]),
        )
    message = PushMessage(note["title"], note["body"], {k: v for k, v in note["data"].items() if v})
    provider = deps.push()
    failures: List[str] = []
    for device in devices:  # no transaction is open while we talk to the push service
        try:
            outcome = await provider.send(device["apns_token"], message)
        except PushError as exc:
            failures.append(str(exc))
            continue
        async with db.transaction() as conn:
            if outcome.invalid_token:
                await execute(
                    conn, "UPDATE devices SET apns_token = NULL WHERE id = %s", (device["id"],)
                )
            await execute(
                conn,
                "UPDATE push_notifications SET delivered_to = array_append(delivered_to, %s) "
                "WHERE id = %s",
                (device["id"], nid),
            )
    if failures:
        raise PushError("; ".join(failures)[:500])  # the job is retried, served devices skipped
    async with db.transaction() as conn:
        await execute(conn, "UPDATE push_notifications SET sent_at = now() WHERE id = %s", (nid,))
