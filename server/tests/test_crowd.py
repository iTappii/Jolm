"""Ш-47: own crowd data. Check-ins and reports, aggregation, thresholds, planner use."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr

from app import worker
from app.chat.brief import today_in_region
from app.config import get_settings
from app.crowd import service
from app.crowd.service import ProfileCrowd
from app.db import fetch_all, fetch_one
from app.live import clock
from app.planner.build import build_plan
from app.planner.candidates import select_candidates
from app.routing import FakeRouter
from tests.conftest import TransactionalDatabase
from tests.test_chat import sign_in
from tests.test_places import add_place
from tests.test_planner_candidates import brief, fixture_places, names
from tests.test_trips import seed_world

LON, LAT = 76.9550, 43.2550
# Wednesday 2026-12-02, 11:30 in Almaty (UTC+5)
NOW = datetime(2026, 12, 2, 6, 30, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixtures(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    clock.set_clock(lambda: NOW)
    yield
    clock.set_clock(None)


def body(**extra):
    return dict({"lat": LAT, "lon": LON}, **extra)


async def test_checkin_needs_a_person_at_the_place(client, conn):
    place = await add_place(conn, "Парк", LON, LAT, popularity=5)
    url = "/v1/places/%s/checkin" % place
    assert (await client.post(url, json=body())).status_code == 401
    headers = await sign_in(conn)

    near = await client.post(url, json=body(lat=LAT + 0.0005), headers=headers)  # about 55 m
    assert near.status_code == 200, near.text
    assert near.json()["recorded"] is True and 40 <= near.json()["distance_m"] <= 70
    assert near.headers["cache-control"] == "no-store"

    far = await client.post(url, json=body(lat=LAT + 0.01), headers=headers)  # about 1.1 km
    assert far.status_code == 422 and far.json()["error"]["code"] == "too_far_from_place"
    assert (await client.post(url, json={"lat": 99, "lon": 0}, headers=headers)).status_code == 422
    missing = "/v1/places/00000000-0000-0000-0000-000000000000/checkin"
    assert (await client.post(missing, json=body(), headers=headers)).status_code == 404
    rows = await fetch_all(conn, "SELECT kind, level, distance_m FROM place_crowd_reports")
    assert [(r["kind"], r["level"]) for r in rows] == [("checkin", None)]  # only the near one


async def test_location_is_not_stored(conn):
    columns = await fetch_all(
        conn,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'place_crowd_reports'",
    )
    names_ = {c["column_name"] for c in columns}
    assert "distance_m" in names_ and not {"lat", "lon", "geom", "location"} & names_


async def test_repeat_is_answered_not_stored_and_the_daily_limit_holds(client, conn, monkeypatch):
    place = await add_place(conn, "Парк", LON, LAT)
    other = await add_place(conn, "Сквер", LON, LAT + 0.0003)
    headers = await sign_in(conn)
    checkin = "/v1/places/%s/checkin" % place
    first = await client.post(checkin, json=body(), headers=headers)
    again = await client.post(checkin, json=body(), headers=headers)
    assert first.json()["recorded"] is True and again.json()["recorded"] is False
    clock.set_clock(lambda: NOW + service.CHECKIN_REPEAT + timedelta(minutes=1))
    assert (await client.post(checkin, json=body(), headers=headers)).json()["recorded"] is True

    report = "/v1/places/%s/crowd" % place
    for level in ("busy", "empty"):  # the second is a repeat inside two hours
        response = await client.post(report, json=body(level=level), headers=headers)
        assert response.status_code == 200
    rows = await fetch_all(conn, "SELECT level FROM place_crowd_reports WHERE kind = 'crowd'")
    assert [r["level"] for r in rows] == [2]
    bad = await client.post(report, json=body(level="packed"), headers=headers)
    assert bad.status_code == 422

    monkeypatch.setattr(service, "DAILY_LIMIT", 3)  # 3 rows exist: two check-ins and one report
    limited = await client.post("/v1/places/%s/checkin" % other, json=body(), headers=headers)
    assert limited.status_code == 429 and limited.headers["retry-after"] == str(86400 - 31 * 60)
    repeat = await client.post(checkin, json=body(), headers=headers)
    assert repeat.status_code == 200 and repeat.json()["recorded"] is False
    second_user = await sign_in(conn, "b@example.com")
    ok = await client.post("/v1/places/%s/checkin" % other, json=body(), headers=second_user)
    assert ok.status_code == 200  # the limit is per person


async def add_report(conn, place, uid, level, at, kind="crowd"):
    await conn.execute(
        "INSERT INTO place_crowd_reports (place_id, user_id, kind, level, distance_m, created_at)"
        " VALUES (%s, %s, %s, %s, 10, %s)",
        (place, uid, kind, level, at),
    )


async def a_user(conn):
    return (await fetch_one(conn, "INSERT INTO users (locale) VALUES ('en') RETURNING id"))["id"]


async def test_account_deletion_removes_own_reports_and_checkins(client, conn):
    place = await add_place(conn, "Парк", LON, LAT)
    first = await sign_in(conn)
    second = await sign_in(conn, "b@example.com")
    for headers in (first, second):
        for path, payload in (("checkin", body()), ("crowd", body(level="empty"))):
            response = await client.post(
                f"/v1/places/{place}/{path}", json=payload, headers=headers
            )
            assert response.status_code == 200
    assert (await client.delete("/v1/me", headers=first)).status_code == 204
    other = (await client.get("/v1/me", headers=second)).json()["id"]
    rows = await fetch_all(
        conn, "SELECT user_id::text, kind FROM place_crowd_reports ORDER BY kind"
    )
    assert rows == [{"user_id": other, "kind": kind} for kind in ("checkin", "crowd")]


async def test_aggregation_groups_by_local_weekday_and_hour_with_decay(conn):
    place = await add_place(conn, "Парк", LON, LAT)
    uid = await a_user(conn)
    # Wednesday 2026-12-02 11:xx Almaty = 06:xx UTC; two reports in one cell
    await add_report(conn, place, uid, 2, NOW - timedelta(minutes=5))
    await add_report(conn, place, uid, 0, NOW - timedelta(minutes=10))
    # the same weekday and hour two weeks earlier (half-life): weight 0.5
    await add_report(conn, place, uid, 0, NOW - timedelta(days=14))
    # Tuesday 19:30 UTC = Wednesday 00:30 in Almaty.
    await add_report(conn, place, uid, 1, datetime(2026, 12, 1, 19, 30, tzinfo=timezone.utc))
    await add_report(conn, place, uid, None, NOW, kind="checkin")  # not part of the level

    cells = await service.aggregate(conn, NOW)
    rows = await fetch_all(
        conn, "SELECT weekday, hour, level, samples FROM place_crowd_profile ORDER BY weekday, hour"
    )
    assert cells == len(rows) == 2
    midnight, wed = rows
    assert (wed["weekday"], wed["hour"], wed["samples"]) == (2, 11, 3)
    # weights ~1, ~1, 0.5: level = (1*1 + 0 + 0)/(2.5) ~ 0.4
    assert wed["level"] == pytest.approx(0.4, abs=0.01)
    assert (midnight["weekday"], midnight["hour"], midnight["samples"], midnight["level"]) == (
        2,
        0,
        1,
        0.5,
    )

    # the job rebuilds from scratch and drops reports past the window; check-ins stay
    await add_report(conn, place, uid, 2, NOW - timedelta(days=service.WINDOW_DAYS + 1))
    await service.aggregate(conn, NOW)
    left = await fetch_all(conn, "SELECT kind FROM place_crowd_reports ORDER BY kind")
    assert [r["kind"] for r in left] == ["checkin"] + ["crowd"] * 4
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM place_crowd_profile"))["n"] == 2


async def test_the_worker_job_is_registered_and_scheduled(conn):
    assert "crowd.aggregate" in worker._HANDLERS
    assert any(s.kind == "crowd.aggregate" for s in worker.SCHEDULES)
    place = await add_place(conn, "Парк", LON, LAT)
    uid = await a_user(conn)
    await add_report(conn, place, uid, 1, NOW - timedelta(hours=1))
    await worker._HANDLERS["crowd.aggregate"](conn, {})
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM place_crowd_profile"))["n"] == 1


async def fill_profile(conn, place, samples, level=1.0, weekday=2, hour=11):
    await conn.execute(
        "INSERT INTO place_crowd_profile (place_id, weekday, hour, level, samples)"
        " VALUES (%s, %s, %s, %s, %s)",
        (place, weekday, hour, level, samples),
    )


async def test_card_shows_crowd_only_with_enough_data(client, conn):
    place = await add_place(conn, "Парк", LON, LAT)
    card = (await client.get("/v1/places/%s" % place)).json()
    assert card["crowd"] is None  # no data: no block

    await fill_profile(conn, place, service.MIN_PLACE_SAMPLES - 1)
    assert (await client.get("/v1/places/%s" % place)).json()["crowd"] is None  # still too few

    await fill_profile(conn, place, 1, level=0.2, weekday=2, hour=15)  # reaches the threshold
    await fill_profile(conn, place, 1, level=0.9, weekday=4, hour=11)  # another weekday: not shown
    crowd = (await client.get("/v1/places/%s" % place)).json()["crowd"]
    assert crowd["samples"] == service.MIN_PLACE_SAMPLES + 1
    assert crowd["now"] == {"level": 1.0, "label": "busy", "samples": 4}  # Wed 11:00
    # hour 15 has one report only: below MIN_CELL_SAMPLES, not shown
    assert [c["hour"] for c in crowd["today"]] == [11]
    assert crowd["updated_at"]


async def test_planner_uses_the_profile_for_quiet_travellers(conn):
    ids = await fixture_places(conn)
    medeu = ids["Медеу"]
    crowd = await ProfileCrowd.load(conn)
    assert crowd.level(medeu) is None  # no data

    plain = await select_candidates(conn, brief(crowd_tolerance=0))
    await fill_profile(conn, medeu, service.MIN_PLACE_SAMPLES - 1, level=1.0, hour=12)
    await fill_profile(conn, medeu, 3, level=0.0, hour=3)  # night reports cannot qualify daytime
    assert (await ProfileCrowd.load(conn)).level(medeu) is None  # below the threshold: unknown
    below = await select_candidates(
        conn, brief(crowd_tolerance=0), crowd=await ProfileCrowd.load(conn)
    )
    assert names(below.activities) == names(plain.activities)  # no data, no change

    await fill_profile(conn, medeu, 1, level=1.0, hour=13)
    crowd = await ProfileCrowd.load(conn)
    assert crowd.level(medeu) == pytest.approx(1.0)
    quiet = await select_candidates(conn, brief(crowd_tolerance=0), crowd=crowd)
    relaxed = await select_candidates(conn, brief(crowd_tolerance=4), crowd=crowd)
    assert names(plain.activities)[0] == "Медеу" == names(relaxed.activities)[0]
    assert names(quiet.activities)[0] != "Медеу" and "Медеу" in names(quiet.activities)
    medeu_score = next(c for c in quiet.activities if c.place.id == medeu).score
    assert medeu_score.crowd == 1.0


async def test_build_plan_reads_the_profile(conn):
    """The real `build_plan` passes the DB-backed source (not `UnknownCrowd`) to the planner."""
    await seed_world(conn)
    medeu = await add_place(conn, "Медеу-Тест", 77.0587, 43.1573, "mountain", "active", 99)
    await fill_profile(conn, medeu, 8, level=1.0, hour=12)

    db = TransactionalDatabase(conn)
    start = today_in_region() + timedelta(days=10)
    base = {
        "start_date": start, "end_date": start + timedelta(days=1), "budget_kzt": 900000,
        "has_accommodation": True, "must_haves": [], "interests": [], "pace": "normal",
    }  # fmt: skip
    quiet = await build_plan(db, dict(base, crowd_tolerance=0), FakeRouter())
    relaxed = await build_plan(db, dict(base, crowd_tolerance=4), FakeRouter())
    q = {c.place.id: c.score.crowd for c in quiet.selection.activities}
    assert q[medeu] == 1.0  # the profile reached the scoring
    assert medeu in {c.place.id for c in relaxed.selection.activities}
