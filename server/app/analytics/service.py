"""Analytics (Ш-50): event ingest, server-side events, the visit metric and its reports.

Raw, parameterized SQL. The metric "a tourist really came" lives in the SQL views of migration
0024 (`analytics_visits`, `analytics_actions`); this module only reads them for a period.
"""

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.analytics import events
from app.analytics.schemas import EventBatch
from app.db import execute, fetch_all, fetch_one
from app.routing.service import ALMATY_TZ

# A check-in counts as a visit inside the trip item's time window +- this much. The same
# number is in the `analytics_visits` view (a test keeps them equal).
VISIT_TOLERANCE = timedelta(hours=1)
# Events older than this (by the device's own clock) are not accepted: a long-offline queue
# would otherwise rewrite history.
MAX_EVENT_AGE = timedelta(days=7)
DEFAULT_PERIOD_DAYS = 30
REPORT_LIMIT = 100

INSERT_EVENT = """
INSERT INTO analytics_events
    (name, source, client_event_id, install_id, user_id, place_id, trip_id, props, occurred_at,
     received_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
ON CONFLICT (install_id, client_event_id) DO NOTHING
"""
# One place_shown per (trip, place): a rebuild of the trip shows the same place again, which
# is not a new impression.
INSERT_PLACES_SHOWN = """
INSERT INTO analytics_events
    (name, source, user_id, place_id, trip_id, props, occurred_at, received_at)
SELECT 'place_shown', 'server', %(user)s, p.place_id, %(trip)s, %(props)s::jsonb, %(now)s, %(now)s
FROM (SELECT DISTINCT place_id FROM trip_items WHERE trip_id = %(trip)s AND variant = 'main') p
WHERE NOT EXISTS (
    SELECT 1 FROM analytics_events e
    WHERE e.name = 'place_shown' AND e.trip_id = %(trip)s AND e.place_id = p.place_id)
"""
COUNT_PLACES = (
    "SELECT count(DISTINCT place_id) AS n FROM trip_items WHERE trip_id = %s AND variant = 'main'"
)
ANONYMIZE = """
UPDATE analytics_events SET user_id = NULL, install_id = NULL
WHERE user_id = %s OR install_id IN (
    SELECT install_id FROM analytics_events WHERE user_id = %s AND install_id IS NOT NULL)
"""
KNOWN_PLACES = "SELECT id FROM places WHERE id = ANY(%s)"

PLACE_REPORT = """
WITH visits AS (
    SELECT place_id, count(*) AS visits, count(DISTINCT user_id) AS tourists,
           max(visited_at) AS last_visit_at
    FROM analytics_visits WHERE visited_at >= %(start)s AND visited_at < %(end)s GROUP BY place_id
), checkins AS (
    SELECT place_id, count(*) AS n FROM place_crowd_reports
    WHERE kind = 'checkin' AND created_at >= %(start)s AND created_at < %(end)s GROUP BY place_id
), shown AS (
    SELECT place_id, count(*) AS n FROM analytics_events
    WHERE name = 'place_shown' AND place_id IS NOT NULL
      AND occurred_at >= %(start)s AND occurred_at < %(end)s GROUP BY place_id
), directions AS (
    SELECT place_id, count(*) AS n FROM analytics_events
    WHERE name = 'directions_start' AND place_id IS NOT NULL
      AND occurred_at >= %(start)s AND occurred_at < %(end)s GROUP BY place_id
)
SELECT p.id AS place_id, p.name_ru, p.name_en,
       coalesce(v.visits, 0) AS visits, coalesce(v.tourists, 0) AS tourists,
       coalesce(c.n, 0) AS checkins, coalesce(s.n, 0) AS shown,
       coalesce(d.n, 0) AS directions, v.last_visit_at
FROM places p
LEFT JOIN visits v ON v.place_id = p.id
LEFT JOIN checkins c ON c.place_id = p.id
LEFT JOIN shown s ON s.place_id = p.id
LEFT JOIN directions d ON d.place_id = p.id
WHERE coalesce(v.visits, 0) + coalesce(c.n, 0) + coalesce(s.n, 0) + coalesce(d.n, 0) > 0
ORDER BY visits DESC, shown DESC, p.name_ru, p.id
LIMIT %(limit)s
"""
# Funnel: step 1 counts devices, the other steps count accounts (`person` for directions: a
# guest can ask for directions too). Each step is a distinct count over the period.
FUNNEL = """
SELECT
  count(DISTINCT install_id) FILTER (WHERE name IN ('app_install', 'app_launch')) AS devices,
  count(DISTINCT user_id) FILTER (WHERE name = 'sign_in') AS signed_in,
  count(DISTINCT user_id) FILTER (WHERE name = 'route_created') AS route_created,
  count(DISTINCT person) FILTER (WHERE name = 'directions_start') AS directions_started,
  count(DISTINCT user_id) FILTER (WHERE name = 'trip_downloaded') AS route_downloaded,
  count(DISTINCT user_id) FILTER (WHERE name = 'checkin') AS checked_in,
  count(DISTINCT user_id) FILTER (WHERE name = 'visit') AS visited,
  count(*) FILTER (WHERE name = 'app_install') AS installs,
  count(*) FILTER (WHERE name = 'visit') AS visits
FROM analytics_actions WHERE occurred_at >= %(start)s AND occurred_at < %(end)s
"""


def occurred_at(
    now: datetime, sent_at: Optional[datetime], ts: Optional[datetime]
) -> Optional[datetime]:
    """When the event happened by the server's clock, or None when it is too old.

    The device clock may be off, so only the AGE of the event on the device is used:
    `sent_at - ts` (the batch's own timestamp as the reference). Without `sent_at` the age is
    measured against the server clock. A timestamp from the future (an age below zero) means
    "just now".
    """
    if ts is None:
        return now
    age = (sent_at if sent_at is not None else now) - ts
    if age < timedelta(0):
        age = timedelta(0)
    if age > MAX_EVENT_AGE:
        return None
    return now - age


async def record_server(
    conn,
    name: str,
    now: datetime,
    user_id: Optional[UUID] = None,
    place_id: Optional[UUID] = None,
    trip_id: Optional[UUID] = None,
    props: Optional[Dict[str, Any]] = None,
) -> None:
    """An event the server itself knows about (no install id: the request may not have one)."""
    await execute(
        conn,
        INSERT_EVENT,
        (
            name, "server", None, None, user_id, place_id, trip_id,
            json.dumps(events.clean_props(name, props)), now, now,
        ),
    )  # fmt: skip


async def record_route(
    conn, user_id: UUID, trip_id: UUID, version: int, days: int, now: datetime
) -> None:
    """`route_created` plus one `place_shown` per place the trip shows for the first time."""
    row = await fetch_one(conn, COUNT_PLACES, (trip_id,))
    await record_server(
        conn, "route_created", now, user_id, None, trip_id,
        {"version": version, "days": days, "places": row["n"]},
    )  # fmt: skip
    await execute(
        conn,
        INSERT_PLACES_SHOWN,
        {
            "user": user_id,
            "trip": trip_id,
            "now": now,
            "props": json.dumps(events.clean_props("place_shown", {"version": version})),
        },
    )


async def ingest(
    conn, install_id: UUID, user_id: Optional[UUID], batch: EventBatch, now: datetime
) -> Dict[str, int]:
    """Store a batch of client events. Returns {"accepted", "duplicates", "rejected"}.

    A bad event (unknown or server-only name, too old, unknown place) is rejected on its own; the
    rest of the batch is stored. A repeat of an event id for this install is a duplicate.
    """
    wanted = {
        e.place_id for e in batch.events if e.place_id and e.name in events.CLIENT_PLACE_EVENTS
    }
    known = set()
    if wanted:
        rows = await fetch_all(conn, KNOWN_PLACES, (list(wanted),))
        known = {r["id"] for r in rows}
    accepted = duplicates = rejected = 0
    for event in batch.events:
        when = occurred_at(now, batch.sent_at, event.ts)
        if event.name not in events.CLIENT_EVENTS or when is None:
            rejected += 1
            continue
        place_id = event.place_id if event.name in events.CLIENT_PLACE_EVENTS else None
        if place_id is not None and place_id not in known:
            rejected += 1
            continue
        props = events.clean_props(event.name, event.props)
        stored = await execute(
            conn,
            INSERT_EVENT,
            (
                event.name, "client", event.id, install_id, user_id, place_id, None,
                json.dumps(props), when, now,
            ),
        )  # fmt: skip
        if stored:
            accepted += 1
        else:
            duplicates += 1
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


async def anonymize_user(conn, user_id: UUID) -> None:
    """Account deletion: cut every analytics event from the person. The user's events and every
    other event of the same installs lose `user_id` and `install_id`; the rows (counts) stay.
    Check-ins and trips go with the account by their own cascade."""
    await execute(conn, ANONYMIZE, (user_id, user_id))


def period(start: Optional[date], end: Optional[date], today: date):
    """Local (Almaty) calendar days, both inclusive -> [start, end) timestamps and the dates.

    Defaults to the last DEFAULT_PERIOD_DAYS ending today; an inverted range is swapped.
    """
    end = end or today
    start = start or end - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if start > end:
        start, end = end, start
    lo = datetime.combine(start, time.min, tzinfo=ALMATY_TZ)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=ALMATY_TZ)
    return start, end, lo, hi


async def place_visits_report(
    conn, lo: datetime, hi: datetime, limit: int = REPORT_LIMIT
) -> List[Dict[str, Any]]:
    """Visits per place over [lo, hi): visits (check-in inside the trip window), distinct
    tourists, all check-ins, times the place was shown in a route, directions started."""
    return await fetch_all(conn, PLACE_REPORT, {"start": lo, "end": hi, "limit": limit})


async def funnel(conn, lo: datetime, hi: datetime) -> Dict[str, int]:
    return dict(await fetch_one(conn, FUNNEL, {"start": lo, "end": hi}))
