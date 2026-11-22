"""Ш-50: analytics events, server-side events, the visit metric, reports, anonymization."""

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr

from app.analytics import events, service
from app.config import get_settings
from app.db import fetch_all, fetch_one
from app.live import clock
from app.regions import default_region
from tests.test_admin import logged_in
from tests.test_chat import sign_in
from tests.test_places import add_place
from tests.test_trips_offline import offline
from tests.test_trips_read import built

# Wednesday 2026-12-02, 11:30 in Almaty (UTC+5)
NOW = datetime(2026, 12, 2, 6, 30, tzinfo=timezone.utc)
INSTALL = "11111111-1111-4111-8111-111111111111"
URL = "/v1/analytics/events"


@pytest.fixture(autouse=True)
def fixtures(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    clock.set_clock(lambda: NOW)
    yield
    clock.set_clock(None)


def hdr(install=INSTALL, extra=None):
    return dict({"X-Install-ID": install}, **(extra or {}))


def ev(name="app_launch", **kw):
    return dict({"id": str(uuid.uuid4()), "name": name}, **kw)


async def post(client, events_list, headers=None, **body):
    return await client.post(
        URL, json=dict({"events": events_list}, **body), headers=headers or hdr()
    )


async def rows(conn, where="true"):
    return await fetch_all(
        conn,
        "SELECT * FROM analytics_events WHERE %s ORDER BY id" % where,  # noqa: S608
    )


async def user_id_of(conn, headers):
    token = headers["Authorization"].split()[1]
    from app.auth import sessions

    return (await sessions.current_user(conn, token))["id"]


# --- ingest ----------------------------------------------------------------------------------


async def test_client_events_are_stored_with_whitelisted_props_only(client, conn):
    place = await add_place(conn, "Парк", 76.95, 43.25)
    batch = [
        ev("app_install", props={"app_version": "1.0", "locale": "ru", "email": "a@b.c"}),
        ev("app_launch", props={"app_version": "x" * 41, "nested": {"a": 1}}),
        ev("directions_start", place_id=str(place), props={"mode": "scooter", "lat": 43.2}),
        ev("directions_start", props={"mode": "rocket"}),
    ]
    response = await post(client, batch)
    assert response.status_code == 200, response.text
    assert response.json() == {"accepted": 4, "duplicates": 0, "rejected": 0}
    assert response.headers["cache-control"] == "no-store"
    stored = await rows(conn)
    assert [r["name"] for r in stored] == [
        "app_install", "app_launch", "directions_start", "directions_start",
    ]  # fmt: skip
    assert [r["props"] for r in stored] == [
        {"app_version": "1.0", "locale": "ru"}, {}, {"mode": "scooter"}, {},
    ]  # fmt: skip
    assert stored[2]["place_id"] == place and stored[3]["place_id"] is None
    assert {str(r["install_id"]) for r in stored} == {INSTALL}
    assert all(r["source"] == "client" and r["user_id"] is None for r in stored)


async def test_bad_events_are_rejected_one_by_one(client, conn):
    place = await add_place(conn, "Парк", 76.95, 43.25)
    batch = [
        ev("route_created"),  # server-only: a client must not inflate the funnel
        ev("made_up"),
        ev("directions_start", place_id=str(uuid.uuid4())),  # unknown place
        ev("app_launch", place_id=str(place)),  # place not allowed here: dropped, event kept
        ev("app_launch", ts=(NOW - timedelta(days=8)).isoformat()),  # too old
        ev("app_launch"),
    ]
    response = await post(client, batch)
    assert response.json() == {"accepted": 2, "duplicates": 0, "rejected": 4}
    stored = await rows(conn)
    assert [r["name"] for r in stored] == ["app_launch", "app_launch"]
    assert all(r["place_id"] is None for r in stored)


async def test_a_retried_batch_is_not_counted_twice(client, conn):
    batch = [ev("app_launch"), ev("app_install")]
    assert (await post(client, batch)).json()["accepted"] == 2
    again = await post(client, batch + [ev("app_launch")])
    assert again.json() == {"accepted": 1, "duplicates": 2, "rejected": 0}
    assert len(await rows(conn)) == 3
    # the same event id from another install is another event
    other = await post(client, batch, hdr("22222222-2222-4222-8222-222222222222"))
    assert other.json()["accepted"] == 2


async def test_the_user_comes_from_the_bearer_and_a_bad_bearer_is_ignored(client, conn):
    headers = await sign_in(conn)
    assert (await post(client, [ev()], hdr(extra=headers))).status_code == 200
    bad = await post(client, [ev()], hdr(extra={"Authorization": "Bearer nope"}))
    assert bad.status_code == 200 and bad.json()["accepted"] == 1
    stored = await rows(conn, "source = 'client'")
    assert stored[0]["user_id"] == await user_id_of(conn, headers) and stored[1]["user_id"] is None


async def test_request_limits(client, conn):
    assert (await client.post(URL, json={"events": [ev()]})).status_code == 400  # no install id
    no_id = await client.post(URL, json={"events": [ev()]}, headers={"X-Install-ID": "nope"})
    assert no_id.status_code == 400 and no_id.json()["error"]["code"] == "invalid_install_id"
    assert (await post(client, [])).status_code == 422
    assert (await post(client, [ev()] * 51)).status_code == 422
    assert (await post(client, [{"name": "app_launch"}])).status_code == 422  # no id
    assert (await post(client, [ev(ts="2026-12-02T10:00:00")])).status_code == 422  # no zone
    assert (await post(client, [dict(ev(), extra=1)])).status_code == 422
    big = await post(client, [ev(props={"x": "y" * 40_000})])
    assert big.status_code == 413 and big.json()["error"]["code"] == "payload_too_large"
    assert await rows(conn) == []


async def test_rate_limit_per_install(client, conn):
    from app.analytics.api import make_limiters

    settings = get_settings().model_copy(update={"analytics_install_limit": 2})
    client._transport.app.state.analytics_limiters = make_limiters(settings)
    assert (await post(client, [ev()])).status_code == 200
    assert (await post(client, [ev()])).status_code == 200
    third = await post(client, [ev()])
    assert third.status_code == 429 and int(third.headers["retry-after"]) >= 1
    other = await post(client, [ev()], hdr("33333333-3333-4333-8333-333333333333"))
    assert other.status_code == 200


# --- clock skew ------------------------------------------------------------------------------


def test_occurred_at_uses_the_age_on_the_device_not_its_clock():
    skew = timedelta(hours=3)  # the device clock is 3 hours ahead
    sent = NOW + skew
    assert service.occurred_at(NOW, sent, sent - timedelta(minutes=10)) == NOW - timedelta(
        minutes=10
    )
    assert service.occurred_at(NOW, None, None) == NOW
    assert service.occurred_at(NOW, None, NOW - timedelta(hours=1)) == NOW - timedelta(hours=1)
    # from the future: just now
    assert service.occurred_at(NOW, sent, sent + timedelta(minutes=5)) == NOW
    assert service.occurred_at(NOW, None, NOW + timedelta(days=30)) == NOW
    edge = sent - service.MAX_EVENT_AGE
    assert service.occurred_at(NOW, sent, edge) == NOW - service.MAX_EVENT_AGE
    assert service.occurred_at(NOW, sent, edge - timedelta(seconds=1)) is None


async def test_event_time_is_corrected_for_a_wrong_device_clock(client, conn):
    skew = timedelta(hours=3)
    body = {"sent_at": (NOW + skew).isoformat()}
    ts = (NOW + skew - timedelta(minutes=45)).isoformat()
    assert (await post(client, [ev(ts=ts)], **body)).json()["accepted"] == 1
    row = (await rows(conn))[0]
    assert row["occurred_at"] == NOW - timedelta(minutes=45) and row["received_at"] == NOW


def test_whitelist_covers_every_event_and_clean_props_is_strict():
    assert set(events.PROPS) == set(events.CLIENT_EVENTS) | set(events.SERVER_EVENTS)
    assert events.clean_props("route_created", {"days": True, "version": 2, "x": 1}) == {
        "version": 2
    }
    assert events.clean_props("nope", {"a": 1}) == {}


# --- server-side events ----------------------------------------------------------------------


async def test_server_writes_sign_in_route_places_and_download(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    me = await user_id_of(conn, headers)
    trip = ready["trip_id"]
    sign = await rows(conn, "name = 'sign_in'")
    assert len(sign) == 1 and sign[0]["user_id"] == me and sign[0]["source"] == "server"
    assert sign[0]["props"] == {"provider": "email", "new_user": True}
    route = await rows(conn, "name = 'route_created'")
    assert len(route) == 1 and str(route[0]["trip_id"]) == trip
    places = await fetch_all(
        conn, "SELECT DISTINCT place_id FROM trip_items WHERE trip_id = %s", (trip,)
    )
    assert route[0]["props"]["places"] == len(places) > 0 and route[0]["props"]["version"] == 1
    shown = await rows(conn, "name = 'place_shown'")
    assert sorted(r["place_id"] for r in shown) == sorted(p["place_id"] for p in places)

    first = await offline(chat_env, headers, trip, "en")
    assert first.status_code == 200
    again = await offline(chat_env, headers, trip, "en", **{"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    downloads = await rows(conn, "name = 'trip_downloaded'")
    assert len(downloads) == 1 and downloads[0]["user_id"] == me  # the 304 is not a download
    assert (await offline(chat_env, headers, uuid.uuid4())).status_code == 404
    assert len(await rows(conn, "name = 'trip_downloaded'")) == 1


# --- the visit metric ------------------------------------------------------------------------


async def make_user(conn):
    row = await fetch_one(conn, "INSERT INTO users (locale) VALUES ('en') RETURNING id")
    return row["id"]


async def make_trip(conn, user, place, starts, minutes=60, variant="main"):
    trip = await fetch_one(
        conn,
        "INSERT INTO trips (user_id, brief, start_date, end_date) VALUES"
        " (%s, '{}'::jsonb, %s, %s) RETURNING id",
        (user, starts.date(), starts.date()),
    )
    await add_item(conn, trip["id"], place, starts, minutes, variant, 1)
    return trip["id"]


async def add_item(conn, trip, place, starts, minutes=60, variant="main", ord_=2):
    await conn.execute(
        "INSERT INTO trip_items (trip_id, variant, day, ord, place_id, kind, starts_at, ends_at,"
        " visit_min) VALUES (%s, %s, %s, %s, %s, 'activity', %s, %s, %s)",
        (trip, variant, starts.date(), ord_, place, starts, starts + timedelta(minutes=minutes),
         minutes),
    )  # fmt: skip


async def checkin(conn, user, place, at):
    await conn.execute(
        "INSERT INTO place_crowd_reports (place_id, user_id, kind, distance_m, created_at)"
        " VALUES (%s, %s, 'checkin', 30, %s)",
        (place, user, at),
    )


async def visits(conn):
    return await fetch_all(conn, "SELECT * FROM analytics_visits ORDER BY visited_at")


async def test_a_visit_is_a_checkin_inside_the_item_window_plus_tolerance(conn):
    place = await add_place(conn, "Музей", 76.95, 43.25)
    user = await make_user(conn)
    start = NOW  # the item: 11:30-12:30 Almaty
    trip = await make_trip(conn, user, place, start)
    tol = service.VISIT_TOLERANCE
    end = start + timedelta(hours=1)
    inside = [start, end, start - tol, end + tol]
    outside = [start - tol - timedelta(seconds=1), end + tol + timedelta(seconds=1)]
    for at in inside + outside:
        await checkin(conn, user, place, at)
    found = await visits(conn)
    assert sorted(v["visited_at"] for v in found) == sorted(inside)
    assert {v["trip_id"] for v in found} == {trip} and {v["user_id"] for v in found} == {user}
    assert all(v["day"] == datetime(2026, 12, 2).date() for v in found[:3])


async def test_the_view_tolerance_matches_the_constant():
    """`analytics_visits` hardcodes the interval; the constant must not drift from it."""
    sql = open("../db/migrations/0024_analytics.sql", encoding="utf-8").read()
    hours = int(service.VISIT_TOLERANCE.total_seconds() // 3600)
    assert service.VISIT_TOLERANCE == timedelta(hours=hours)
    assert len(re.findall(r"interval '%d hours?'" % hours, sql)) == 2


async def test_a_checkin_is_not_a_visit_for_someone_elses_trip_or_another_place_or_variant(conn):
    park, museum, cafe = [await add_place(conn, n, 76.95, 43.25) for n in ("П", "М", "К")]
    alice, bob = await make_user(conn), await make_user(conn)
    await make_trip(conn, alice, museum, NOW)
    await make_trip(conn, bob, cafe, NOW, variant="cheaper")  # an unchosen alternative
    await checkin(conn, bob, museum, NOW)  # Bob has not planned the museum
    await checkin(conn, alice, park, NOW)  # Alice has not planned the park
    await checkin(conn, bob, cafe, NOW)  # only in a 'cheaper' variant
    assert await visits(conn) == []
    await checkin(conn, alice, museum, NOW)
    assert [v["user_id"] for v in await visits(conn)] == [alice]


async def test_one_checkin_is_one_visit_even_when_the_place_is_in_the_trip_twice(conn):
    place = await add_place(conn, "Парк", 76.95, 43.25)
    user = await make_user(conn)
    trip = await make_trip(conn, user, place, NOW)
    await add_item(conn, trip, place, NOW + timedelta(minutes=30))  # overlapping window
    await checkin(conn, user, place, NOW + timedelta(minutes=45))
    assert len(await visits(conn)) == 1


# --- reports ---------------------------------------------------------------------------------


async def seed_report(conn):
    """Three places. Medeu: 3 visits by 2 tourists; Park: 1 visit; Cafe: shown only."""
    medeu = await add_place(conn, "Медеу", 76.95, 43.25)
    park = await add_place(conn, "Парк", 76.95, 43.25)
    cafe = await add_place(conn, "Кафе", 76.95, 43.25)
    alice, bob = await make_user(conn), await make_user(conn)
    ta = await make_trip(conn, alice, medeu, NOW)
    await add_item(conn, ta, park, NOW + timedelta(hours=3))
    tb = await make_trip(conn, bob, medeu, NOW)
    await checkin(conn, alice, medeu, NOW)
    await checkin(conn, alice, medeu, NOW + timedelta(minutes=40))
    await checkin(conn, bob, medeu, NOW)
    await checkin(conn, alice, park, NOW + timedelta(hours=3))
    await checkin(conn, bob, park, NOW)  # Bob did not plan the park: a check-in, not a visit
    for trip, place in ((ta, medeu), (ta, park), (tb, medeu), (tb, cafe)):
        await conn.execute(
            "INSERT INTO analytics_events (name, source, user_id, place_id, trip_id, occurred_at)"
            " VALUES ('place_shown', 'server', NULL, %s, %s, %s)",
            (place, trip, NOW),
        )
    await conn.execute(
        "INSERT INTO analytics_events (name, source, place_id, occurred_at)"
        " VALUES ('directions_start', 'client', %s, %s)",
        (medeu, NOW),
    )
    return medeu, park, cafe, alice, bob


async def test_place_visits_report_for_a_period(conn):
    medeu, park, cafe, *_ = await seed_report(conn)
    start, end, lo, hi = service.period(None, None, NOW.date())
    report = await service.place_visits_report(conn, lo, hi)
    assert [
        (r["name_ru"], r["visits"], r["tourists"], r["checkins"], r["shown"], r["directions"])
        for r in report
    ] == [
        ("Медеу", 3, 2, 3, 2, 1),
        ("Парк", 1, 1, 2, 1, 0),
        ("Кафе", 0, 0, 0, 1, 0),
    ]
    assert report[0]["last_visit_at"] == NOW + timedelta(minutes=40)
    # a period that ends the day before: nothing; a one-day period around today: everything
    day = NOW.astimezone(default_region().tz).date()
    _, _, lo2, hi2 = service.period(day - timedelta(days=5), day - timedelta(days=1), day)
    assert await service.place_visits_report(conn, lo2, hi2) == []
    _, _, lo3, hi3 = service.period(day, day, day)
    assert [r["name_ru"] for r in await service.place_visits_report(conn, lo3, hi3)] == [
        "Медеу", "Парк", "Кафе",
    ]  # fmt: skip
    assert len(await service.place_visits_report(conn, lo, hi, limit=1)) == 1


def test_period_defaults_swaps_and_uses_local_days():
    today = datetime(2026, 12, 2).date()
    start, end, lo, hi = service.period(None, None, today)
    assert (end, (end - start).days) == (today, service.DEFAULT_PERIOD_DAYS - 1)
    start, end, lo, hi = service.period(today, today - timedelta(days=2), today)
    assert start < end
    assert lo.utcoffset() == timedelta(hours=5) and hi - lo == timedelta(days=3)


async def test_funnel_counts_people_per_step(conn):
    medeu, park, cafe, alice, bob = await seed_report(conn)
    for name, user, install in [
        ("app_launch", None, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("app_install", None, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("app_launch", None, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        ("sign_in", alice, None), ("sign_in", alice, None), ("sign_in", bob, None),
        ("route_created", alice, None), ("route_created", bob, None),
        ("directions_start", alice, None),
        ("directions_start", None, "cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        ("trip_downloaded", alice, None),
    ]:  # fmt: skip
        await conn.execute(
            "INSERT INTO analytics_events (name, source, user_id, install_id, occurred_at)"
            " VALUES (%s, 'server', %s, %s, %s)",
            (name, user, install, NOW),
        )
    _, _, lo, hi = service.period(None, None, NOW.date())
    assert await service.funnel(conn, lo, hi) == {
        "devices": 2, "signed_in": 2, "route_created": 2, "directions_started": 2,
        "route_downloaded": 1, "checked_in": 2, "visited": 2, "installs": 1, "visits": 4,
    }  # fmt: skip


# --- admin page ------------------------------------------------------------------------------


async def test_admin_page_needs_login_and_shows_the_report(client, conn):
    assert (await client.get("/admin/analytics")).status_code == 303
    await seed_report(conn)
    await logged_in(client, conn)
    page = await client.get("/admin/analytics?from=2026-12-01&to=2026-12-03")
    assert page.status_code == 200, page.text
    assert (
        "Медеу" in page.text and "Реально пришли" in page.text and "2026-12-02 12:10" in page.text
    )
    empty = await client.get("/admin/analytics?from=2025-01-01&to=2025-01-02")
    assert empty.status_code == 200 and "Медеу" not in empty.text
    junk = await client.get("/admin/analytics?from=oops&to=")
    assert junk.status_code == 200


# --- personal data ---------------------------------------------------------------------------


async def test_account_deletion_anonymizes_events_and_drops_checkins(client, conn):
    place = await add_place(conn, "Парк", 76.95, 43.25)
    headers = await sign_in(conn, "gone@example.com")
    other = await sign_in(conn, "stays@example.com")
    gone, stays = await user_id_of(conn, headers), await user_id_of(conn, other)
    mine, theirs = INSTALL, "44444444-4444-4444-8444-444444444444"
    await post(client, [ev("app_launch")], hdr(mine))  # before sign-in: same device, no user
    await post(client, [ev("directions_start")], hdr(mine, headers))
    await post(client, [ev("app_launch")], hdr(theirs, other))
    await checkin(conn, gone, place, NOW)
    await checkin(conn, stays, place, NOW)
    before = len(await rows(conn))

    assert (await client.delete("/v1/me", headers=headers)).status_code == 204

    after = await rows(conn)
    assert len(after) == before  # the counts stay
    assert all(r["user_id"] != gone for r in after)
    assert all(str(r["install_id"]) != mine for r in after)  # the device is cut loose too
    client_rows = [r for r in after if r["source"] == "client"]
    assert [r["name"] for r in client_rows] == ["app_launch", "directions_start", "app_launch"]
    assert [r["install_id"] for r in client_rows] == [None, None, uuid.UUID(theirs)]
    assert [r["user_id"] for r in client_rows] == [None, None, stays]
    left = await fetch_all(conn, "SELECT user_id FROM place_crowd_reports")
    assert [r["user_id"] for r in left] == [stays]


async def test_events_keep_the_place_and_block_its_deletion_without_a_merge(conn):
    place = await add_place(conn, "Парк", 76.95, 43.25)
    await conn.execute(
        "INSERT INTO analytics_events (name, source, place_id, occurred_at)"
        " VALUES ('directions_start', 'client', %s, %s)",
        (place, NOW),
    )
    import psycopg

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        async with conn.transaction():
            await conn.execute("DELETE FROM places WHERE id = %s", (place,))
