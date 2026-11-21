"""Ш-40: weather re-check, proposals, mountain mornings, push, devices. No network, no real push:
fake forecast, fake clock, fake push provider, FakeRouter."""

import json
from datetime import date, datetime, time, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import worker
from app.chat.brief import today_almaty
from app.db import fetch_all, fetch_one
from app.live import clock, deps, rules
from app.live import jobs as live_jobs
from app.providers.weather.base import DayWeather, ForecastView, HourWeather, WeatherUnavailable
from app.push import ApnsProvider, LogPushProvider, PushError, PushMessage, PushOutcome, make_push
from app.routing import FakeRouter
from app.routing.service import ALMATY_TZ
from tests.conftest import TransactionalDatabase
from tests.test_places import add_place
from tests.test_trips import brief_call, build, day, event, signing_secret, start  # noqa: F401
from tests.test_trips_read import get

OUTDOOR = {"Парк Горького", "Кок-Тобе", "Монумент Независимости", "Набережная",
           "Площадь Республики", "Сквер Аллея", "Фонтаны"}  # fmt: skip

CLEAR = HourWeather(15.0, 0.0, 0.0, 8.0, 0)
RAIN = HourWeather(10.0, 0.9, 2.0, 10.0, 61)
STORM = HourWeather(18.0, 0.9, 5.0, 20.0, 95)


def weather_day(d, hour=CLEAR, bad=None):
    """24 hours of `hour`; `bad` = {hour: HourWeather}."""
    return DayWeather(d, tuple((bad or {}).get(h, hour) for h in range(24)))


class FakeWeather:
    def __init__(self, fn):
        self.fn, self.calls = fn, []

    async def forecast(self, lat, lon, days, elevation_m=None):
        self.calls.append((lat, lon, tuple(days), elevation_m))
        out = {d: self.fn(d) for d in days}
        return {d: w for d, w in out.items() if w is not None}


class FailingWeather:
    async def forecast(self, *a, **k):
        raise WeatherUnavailable("down")


class FakePush:
    def __init__(self, invalid=()):
        self.sent, self.invalid = [], set(invalid)

    async def send(self, token, message):
        self.sent.append((token, message))
        if token in self.invalid:
            return PushOutcome(ok=False, invalid_token=True)
        return PushOutcome(ok=True)


@pytest.fixture(autouse=True)
def isolated():
    deps.reset()
    clock.set_clock(None)
    yield
    deps.reset()
    clock.set_clock(None)


def at(d, hh, mm=0):
    return datetime.combine(d, time(hh, mm), tzinfo=ALMATY_TZ)


def today():
    return today_almaty()  # the real date: trips are built relative to it


async def built(chat_env, conn, **brief):
    headers, chat, events, _ = await start(chat_env, conn, **brief)
    ready = event(events, "route_ready")
    return headers, chat, ready["trip_id"]


def outdoor_item(trip):
    for d in trip["days"]:
        for i in d["items"]:
            if i["kind"] == "activity" and i["place"]["name"] in OUTDOOR:
                return d["date"], i
    raise AssertionError("no outdoor stop")


async def recheck(db, trip_id, **extra):
    await live_jobs.weather_recheck(db, dict({"trip_id": trip_id}, **extra))


async def proposals(conn, trip_id):
    return await fetch_all(
        conn,
        "SELECT * FROM trip_change_proposals WHERE trip_id = %s ORDER BY created_at",
        (trip_id,),
    )


def rainy_on(*days):
    wanted = {date.fromisoformat(d) if isinstance(d, str) else d for d in days}
    return lambda d: weather_day(d, RAIN) if d in wanted else weather_day(d)


# --- rules --------------------------------------------------------------------------------
def test_rules_thresholds():
    def hrs(w, upto=24):
        return [w] * upto

    assert rules.stop_problem(hrs(CLEAR), 600, 720) is None
    rain = rules.stop_problem(hrs(RAIN), 600, 720)
    assert (rain.kind, rain.hours, rain.peak) == ("rain", (10, 11), 0.9)
    assert rules.stop_problem(hrs(HourWeather(10, 0.59, 0, 5, 3)), 600, 720) is None  # below 0.6
    assert rules.stop_problem(hrs(HourWeather(10, 0.6, 0, 5, 3)), 600, 720).kind == "rain"
    assert rules.stop_problem(hrs(HourWeather(10, 0, 0, 39.9, 3)), 600, 720) is None
    assert rules.stop_problem(hrs(HourWeather(10, 0, 0, 40, 3)), 600, 720).kind == "wind"
    assert rules.stop_problem(hrs(HourWeather(34.9, 0, 0, 5, 0)), 600, 720) is None
    assert rules.stop_problem(hrs(HourWeather(35, 0, 0, 5, 0)), 600, 720).kind == "heat"
    # one rainy hour out of two = 50% of the visit: suffers; one out of three does not
    mixed = [CLEAR] * 24
    mixed[10] = RAIN
    assert rules.stop_problem(mixed, 600, 720).kind == "rain"
    assert rules.stop_problem(mixed, 600, 780) is None
    # thunder in any hour wins, whatever the share
    mixed[12] = STORM
    assert rules.stop_problem(mixed, 600, 780).kind == "thunderstorm"
    # unknown hours are ignored; nothing known = no problem
    assert rules.stop_problem([None] * 24, 600, 720) is None
    # mountains: weaker wind and frost count
    breeze = HourWeather(5, 0, 0, 32, 0)
    assert rules.stop_problem(hrs(breeze), 600, 720) is None
    assert rules.stop_problem(hrs(breeze), 600, 720, rules.MOUNTAIN_WIND_KMH).kind == "wind"
    frost = HourWeather(-3, 0, 0, 5, 0)
    assert rules.stop_problem(hrs(frost), 600, 720, cold_c=rules.MOUNTAIN_COLD_C).kind == "cold"


# --- build wiring -------------------------------------------------------------------------
async def test_build_trip_uses_the_forecast_and_records_the_check(chat_env, conn):
    fake = FakeWeather(lambda d: weather_day(d))
    chat_env.app.state.weather_provider = fake
    fixed = at(today(), 12)
    clock.set_clock(lambda: fixed)
    headers, chat, trip_id = await built(chat_env, conn)
    assert fake.calls and set(fake.calls[0][2]) == {
        today() + timedelta(days=i) for i in (10, 11, 12)
    }
    row = await fetch_one(conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,))
    assert row["weather_checked_at"] == fixed


async def test_build_trip_without_a_forecast_leaves_the_trip_due(chat_env, conn):
    chat_env.app.state.weather_provider = FailingWeather()
    headers, chat, trip_id = await built(chat_env, conn)
    row = await fetch_one(conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,))
    assert row["weather_checked_at"] is None


# --- re-check -> proposal -> accept -------------------------------------------------------
async def test_rain_on_an_outdoor_stop_creates_one_proposal_message_and_push(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    fake = FakeWeather(rainy_on(rainy_day))
    push = FakePush()
    deps.configure(weather=fake, router=FakeRouter(), push=push)
    now = at(today(), 12)
    clock.set_clock(lambda: now)
    db = TransactionalDatabase(conn)

    await recheck(db, trip_id)
    rows = await proposals(conn, trip_id)
    assert len(rows) == 1
    p = rows[0]
    assert p["status"] == "pending" and p["reason"] == "weather" and p["trip_version"] == 1
    assert str(p["place_id"]) == item["place"]["id"] and p["day"].isoformat() == rainy_day
    assert p["diff"]["problem"]["type"] == "rain"
    checked = await fetch_one(
        conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,)
    )
    assert checked["weather_checked_at"] == now

    msgs = await fetch_all(conn, "SELECT * FROM chat_messages WHERE proposal_id IS NOT NULL")
    assert len(msgs) == 1 and msgs[0]["role"] == "assistant" and msgs[0]["finish"] == "stop"
    assert item["place"]["name"] in msgs[0]["content"] and "forecast" in msgs[0]["content"]
    chat_json = (await chat_env.client.get("/v1/chats/%s" % chat["id"], headers=headers)).json()
    assert chat_json["messages"][-1]["proposal_id"] == str(p["id"])
    note = await fetch_one(conn, "SELECT * FROM push_notifications")
    assert note["kind"] == "weather_proposal" and note["data"]["proposal_id"] == str(p["id"])
    job = await fetch_one(conn, "SELECT payload FROM jobs WHERE kind = 'push.send'")
    assert job["payload"] == {"notification_id": str(note["id"])}

    # a second re-check does not nag: the proposal is still waiting for an answer
    await recheck(db, trip_id, force=True)
    assert len(await proposals(conn, trip_id)) == 1
    assert await fetch_one(conn, "SELECT count(*) AS n FROM push_notifications") == {"n": 1}


async def test_proposal_is_listed_and_accepting_applies_it_and_bumps_the_version(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=FakeRouter(), push=FakePush())
    await recheck(TransactionalDatabase(conn), trip_id)

    listed = await chat_env.client.get("/v1/trips/%s/proposals" % trip_id, headers=headers)
    assert listed.status_code == 200
    body = listed.json()["items"]
    assert len(body) == 1
    p = body[0]
    assert set(p) == {
        "id", "trip_id", "reason", "kind", "status", "trip_version", "day", "to_day", "item_id",
        "problem", "place", "target_place", "created_at", "decided_at",
    }  # fmt: skip
    assert (
        p["status"] == "pending"
        and p["day"] == rainy_day
        and p["place"]["id"] == item["place"]["id"]
    )
    assert p["problem"]["type"] == "rain" and p["problem"]["hours"][0] <= p["problem"]["hours"][1]
    assert p["kind"] == "move_day" and p["to_day"] != rainy_day and p["target_place"] is None

    accepted = await chat_env.client.post("/v1/proposals/%s/accept" % p["id"], headers=headers)
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()
    assert result["version"] == 2 and result["action"] == "move"
    assert result["proposal"] == {"id": p["id"], "status": "accepted"}
    assert set(result["changed_days"]) == {rainy_day, p["to_day"]}
    after = (await get(chat_env, headers, trip_id)).json()
    on_new_day = [
        i["place"]["id"] for d in after["days"] if d["date"] == p["to_day"] for i in d["items"]
    ]
    on_old_day = [
        i["place"]["id"] for d in after["days"] if d["date"] == rainy_day for i in d["items"]
    ]
    assert item["place"]["id"] in on_new_day and item["place"]["id"] not in on_old_day
    again = await chat_env.client.post("/v1/proposals/%s/accept" % p["id"], headers=headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "proposal_decided"
    # no taste signal for a weather swap, and a follow-up re-check is queued
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM user_place_signals"))["n"] == 0
    follow = await fetch_all(conn, "SELECT payload FROM jobs WHERE kind = 'weather.recheck'")
    assert follow and follow[0]["payload"]["force"] is True


async def test_when_every_day_is_rainy_an_indoor_place_replaces_the_stop(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    for n in range(2):  # the seeded world is used up by the plan: add indoor places nearby
        await add_place(conn, "Новый музей %d" % n, 76.95, 43.25 + n * 0.001, "museum", "active", 5)
    deps.configure(weather=FakeWeather(lambda d: weather_day(d, RAIN)), router=FakeRouter(),
                   push=FakePush())  # fmt: skip
    await recheck(TransactionalDatabase(conn), trip_id)
    p = (await proposals(conn, trip_id))[0]
    assert p["kind"] == "replace" and p["target_place_id"] is not None and p["to_day"] is None
    target = await fetch_one(
        conn,
        "SELECT p.name_ru, c.outdoor FROM places p JOIN place_categories c ON c.id = p.category_id "
        "WHERE p.id = %s",
        (p["target_place_id"],),
    )
    assert target["outdoor"] is False
    accepted = await chat_env.client.post("/v1/proposals/%s/accept" % p["id"], headers=headers)
    assert accepted.status_code == 200 and accepted.json()["action"] == "replace"
    after = (await get(chat_env, headers, trip_id)).json()
    names = [
        i["place"]["name"] for d in after["days"] if d["date"] == rainy_day for i in d["items"]
    ]
    assert target["name_ru"] in names and item["place"]["name"] not in names


async def test_a_must_have_is_moved_never_swapped_for_another_place(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn, must_haves=["Парк Горького"])
    trip = (await get(chat_env, headers, trip_id)).json()
    day_, item = next((d["date"], i) for d in trip["days"] for i in d["items"] if i["must_have"])
    deps.configure(weather=FakeWeather(lambda d: weather_day(d, RAIN)), router=FakeRouter(),
                   push=FakePush())  # fmt: skip
    await recheck(TransactionalDatabase(conn), trip_id)
    assert await proposals(conn, trip_id) == []  # rain everywhere: a must-have has no alternative


async def test_stale_proposal_is_expired_and_accept_answers_409(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=FakeRouter(), push=FakePush())
    await recheck(TransactionalDatabase(conn), trip_id)
    p = (await proposals(conn, trip_id))[0]
    other = next(
        i
        for d in trip["days"]
        for i in d["items"]
        if i["id"] != item["id"] and d["date"] != rainy_day
    )
    edit = await chat_env.client.post(
        "/v1/trips/%s/items/%s/remove" % (trip_id, other["id"]), headers=headers
    )
    assert edit.status_code == 200  # the plan changed: version 2
    listed = (await chat_env.client.get("/v1/trips/%s/proposals" % trip_id, headers=headers)).json()
    assert listed["items"][0]["status"] == "expired"
    stale = await chat_env.client.post("/v1/proposals/%s/accept" % p["id"], headers=headers)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "proposal_stale"
    row = await fetch_one(
        conn, "SELECT status FROM trip_change_proposals WHERE id = %s", (p["id"],)
    )
    assert row["status"] == "expired"  # persisted even though the request failed
    assert (await get(chat_env, headers, trip_id)).json()["version"] == 2


async def test_decline_then_the_same_stop_is_not_proposed_again(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=FakeRouter(), push=FakePush())
    db = TransactionalDatabase(conn)
    await recheck(db, trip_id)
    p = (await proposals(conn, trip_id))[0]
    declined = await chat_env.client.post("/v1/proposals/%s/decline" % p["id"], headers=headers)
    assert declined.status_code == 200 and declined.json() == {
        "id": str(p["id"]),
        "status": "declined",
    }
    assert (
        await chat_env.client.post("/v1/proposals/%s/decline" % p["id"], headers=headers)
    ).status_code == 409
    await recheck(db, trip_id, force=True)
    rows = await proposals(conn, trip_id)
    still = [
        r
        for r in rows
        if str(r["place_id"]) == item["place"]["id"] and r["day"].isoformat() == rainy_day
    ]
    assert len(still) == 1  # no second proposal for the declined stop-day
    version = (await get(chat_env, headers, trip_id)).json()["version"]
    assert version == 1  # declining changes nothing


async def test_pending_proposal_expires_when_the_forecast_clears(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=FakeRouter(), push=FakePush())
    db = TransactionalDatabase(conn)
    await recheck(db, trip_id)
    deps.configure(weather=FakeWeather(lambda d: weather_day(d)))  # sunny now
    await recheck(db, trip_id, force=True)
    assert [r["status"] for r in await proposals(conn, trip_id)] == ["expired"]


async def test_proposals_are_private_to_their_owner(chat_env, conn):
    from tests.test_chat import sign_in

    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=FakeRouter(), push=FakePush())
    await recheck(TransactionalDatabase(conn), trip_id)
    p = (await proposals(conn, trip_id))[0]
    stranger = await sign_in(conn, "other@example.com")
    for method, url in (("get", "/v1/trips/%s/proposals" % trip_id),
                        ("post", "/v1/proposals/%s/accept" % p["id"]),
                        ("post", "/v1/proposals/%s/decline" % p["id"])):  # fmt: skip
        response = await getattr(chat_env.client, method)(url, headers=stranger)
        assert response.status_code == 404
    assert (await chat_env.client.get("/v1/trips/%s/proposals" % trip_id)).status_code == 401


async def test_unavailable_forecast_fails_the_job_so_it_is_retried(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    deps.configure(weather=FailingWeather(), router=FakeRouter(), push=FakePush())
    with pytest.raises(WeatherUnavailable):
        await recheck(TransactionalDatabase(conn), trip_id)
    row = await fetch_one(conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,))
    assert row["weather_checked_at"] is None  # not stamped: it stays due


# --- plan-then-apply: no routing under the trip lock (Ш-38 coordinator №1) ----------------
class RacingRouter(FakeRouter):
    """Logs routing calls; can edit the trip (version bump) while the worker is routing."""

    def __init__(self, conn, log, bump):
        super().__init__()
        self.conn, self.log, self.bump, self.calls = conn, log, bump, 0

    async def matrix(self, sources, targets, mode):
        self.calls += 1
        self.log.append("route")
        if self.bump == "always" or (self.bump == "once" and self.calls == 1):
            await self.conn.execute("UPDATE trips SET version = version + 1")
        return await super().matrix(sources, targets, mode)


@pytest.fixture
def lock_log(monkeypatch):
    from app.trips import store as trips_store

    log = []
    real = trips_store.get_trip_row

    async def spy(conn, user_id, trip_id, lock=False):
        if lock:
            log.append("lock")
        return await real(conn, user_id, trip_id, lock=lock)

    monkeypatch.setattr(trips_store, "get_trip_row", spy)
    return log


async def rainy_setup(chat_env, conn, router):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=router, push=FakePush())
    return trip_id, item


async def test_recheck_routes_before_the_trip_is_locked(chat_env, conn, lock_log):
    log = lock_log
    router = RacingRouter(conn, log, None)
    trip_id, item = await rainy_setup(chat_env, conn, router)
    log.clear()
    await recheck(TransactionalDatabase(conn), trip_id)
    assert len(await proposals(conn, trip_id)) == 1
    assert "route" in log and log.count("lock") == 1
    assert log.index("lock") > max(i for i, x in enumerate(log) if x == "route")


async def test_a_trip_edited_while_planning_is_replanned_not_applied_stale(
    chat_env, conn, lock_log
):
    router = RacingRouter(conn, lock_log, "once")
    trip_id, item = await rainy_setup(chat_env, conn, router)
    lock_log.clear()
    await recheck(TransactionalDatabase(conn), trip_id)
    rows = await proposals(conn, trip_id)
    assert len(rows) == 1  # exactly one proposal
    assert rows[0]["trip_version"] == 2  # computed for the plan as it is after the edit
    assert lock_log.count("lock") == 2  # the first attempt stopped at the version check
    assert router.calls >= 2  # planned twice
    checked = await fetch_one(
        conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,)
    )
    assert checked["weather_checked_at"] is not None


async def test_a_trip_that_keeps_changing_fails_the_job_without_writes(chat_env, conn, lock_log):
    router = RacingRouter(conn, lock_log, "always")
    trip_id, item = await rainy_setup(chat_env, conn, router)
    with pytest.raises(live_jobs.TripChanged):
        await recheck(TransactionalDatabase(conn), trip_id)
    assert await proposals(conn, trip_id) == []
    assert await fetch_one(conn, "SELECT count(*) AS n FROM push_notifications") == {"n": 0}
    row = await fetch_one(conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,))
    assert row["weather_checked_at"] is None  # stays due: the worker retries the job
    assert lock_log.count("lock") == live_jobs.RECHECK_ATTEMPTS


async def test_a_stale_plan_does_not_duplicate_a_proposal_made_meanwhile(chat_env, conn):
    from app.live import engine
    from app.trips import store as trips_store

    trip_id, item = await rainy_setup(chat_env, conn, FakeRouter())
    db = TransactionalDatabase(conn)
    now = clock.now()
    row = await fetch_one(conn, "SELECT user_id FROM trips WHERE id = %s", (trip_id,))
    current = await trips_store.get_trip_row(conn, row["user_id"], trip_id)
    forecast = ForecastView(
        await deps.weather(db).forecast(0, 0, [today() + timedelta(days=i) for i in (10, 11, 12)])
    )
    plan = await engine.plan_proposal(conn, FakeRouter(), current, forecast, now)
    assert plan.spec is not None and plan.version == current["version"]
    await recheck(db, trip_id)  # a concurrent run applied its own plan first
    assert len(await proposals(conn, trip_id)) == 1
    locked = await trips_store.get_trip_row(conn, row["user_id"], trip_id, lock=True)
    await live_jobs._apply(conn, locked, plan, now)  # the stale twin must not add another
    assert len(await proposals(conn, trip_id)) == 1
    assert await fetch_one(conn, "SELECT count(*) AS n FROM push_notifications") == {"n": 1}


# --- schedule (fake clock) ----------------------------------------------------------------
async def test_scan_enqueues_trips_due_every_two_days_once_per_day(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    db = TransactionalDatabase(conn)
    now = at(today(), 12)
    clock.set_clock(lambda: now)

    async def scan(moment):
        clock.set_clock(lambda: moment)
        await live_jobs.weather_scan(conn, {})
        return (
            await fetch_one(conn, "SELECT count(*) AS n FROM jobs WHERE kind = 'weather.recheck'")
        )["n"]

    await conn.execute("UPDATE trips SET weather_checked_at = %s", (now - timedelta(hours=47),))
    assert await scan(now) == 0  # checked 47 hours ago: not due
    await conn.execute("UPDATE trips SET weather_checked_at = %s", (now - timedelta(hours=49),))
    assert await scan(now) == 1  # due
    assert await scan(now + timedelta(hours=1)) == 1  # same day: the dedupe key holds
    await conn.execute("DELETE FROM jobs")
    await conn.execute("UPDATE trips SET weather_checked_at = NULL")
    assert await scan(now) == 1  # never checked: due
    await conn.execute("DELETE FROM jobs")
    await conn.execute(
        "UPDATE trips SET start_date = %s, end_date = %s",
        (today() - timedelta(days=3), today() - timedelta(days=1)),
    )
    assert await scan(now) == 0  # the trip is over
    await conn.execute(
        "UPDATE trips SET end_date = %s, status = 'archived'", (today() + timedelta(days=3),)
    )
    assert await scan(now) == 0  # archived
    del db


async def test_recheck_skips_a_trip_checked_recently(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    fake = FakeWeather(lambda d: weather_day(d))
    deps.configure(weather=fake, router=FakeRouter(), push=FakePush())
    now = at(today(), 12)
    clock.set_clock(lambda: now)
    await conn.execute("UPDATE trips SET weather_checked_at = %s", (now - timedelta(hours=5),))
    await recheck(TransactionalDatabase(conn), trip_id)
    assert fake.calls == []  # a duplicate job does not spend a forecast call


async def test_scheduled_scan_jobs_run_through_the_worker(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    deps.configure(
        weather=FakeWeather(lambda d: weather_day(d)), router=FakeRouter(), push=FakePush()
    )
    clock.set_clock(lambda: at(today(), 12))
    db = TransactionalDatabase(conn)
    await worker.enqueue(conn, "weather.scan")
    await worker.process_batch(db)  # scan
    await worker.process_batch(db)  # recheck
    row = await fetch_one(conn, "SELECT weather_checked_at FROM trips WHERE id = %s", (trip_id,))
    assert row["weather_checked_at"] == at(today(), 12)


# --- mountains ----------------------------------------------------------------------------
async def mountain_trip(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    first_day = trip["days"][0]
    item = first_day["items"][0]
    await conn.execute(
        "UPDATE places SET is_mountain = true, elevation_m = 1700 WHERE id = %s",
        (item["place"]["id"],),
    )
    start = datetime.fromisoformat(item["starts_at"])
    return headers, chat, trip_id, date.fromisoformat(first_day["date"]), item, start


async def test_mountain_morning_message_and_push_once_per_trip_day(chat_env, conn):
    headers, chat, trip_id, mday, item, start = await mountain_trip(chat_env, conn)
    fake = FakeWeather(lambda d: weather_day(d, HourWeather(4.0, 0.1, 0.0, 12.0, 1)))
    push = FakePush()
    deps.configure(weather=fake, router=FakeRouter(), push=push)
    db = TransactionalDatabase(conn)

    async def scan_at(moment):
        clock.set_clock(lambda: moment)
        await live_jobs.mountain_scan(conn, {})
        return (
            await fetch_one(conn, "SELECT count(*) AS n FROM jobs WHERE kind = 'mountain.notify'")
        )["n"]

    assert await scan_at(at(mday, 6, 59)) == 0  # before 07:00
    assert await scan_at(start + timedelta(minutes=1)) == 0  # the walk has begun
    assert await scan_at(at(mday - timedelta(days=1), 12)) == 0  # not the day
    assert await scan_at(at(mday, 7, 5)) == 1
    assert await scan_at(at(mday, 7, 20)) == 1  # dedupe: still one job

    clock.set_clock(lambda: at(mday, 7, 5))
    assert await worker.process_batch(db) == 1  # mountain.notify
    msgs = await fetch_all(
        conn, "SELECT content FROM chat_messages WHERE prompt_id = 'system.mountain.v1'"
    )
    assert len(msgs) == 1 and item["place"]["name"] in msgs[0]["content"]
    assert "weather looks fine" in msgs[0]["content"]
    # fresh forecast at the PLACE point and its elevation, for that day
    lat, lon, days, elevation = fake.calls[-1]
    assert days == (mday,) and elevation == 1700 and abs(lat - item["place"]["lat"]) < 1e-6
    note = await fetch_one(conn, "SELECT kind FROM push_notifications")
    assert note["kind"] == "mountain_morning"

    # idempotent: scanning and notifying again adds nothing
    await conn.execute("DELETE FROM jobs WHERE kind = 'mountain.notify'")
    assert await scan_at(at(mday, 7, 30)) == 0
    await live_jobs.mountain_notify(db, {"trip_id": trip_id, "day": mday.isoformat()})
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM push_notifications"))["n"] == 1
    assert (
        len(
            await fetch_all(
                conn, "SELECT 1 FROM chat_messages WHERE prompt_id = 'system.mountain.v1'"
            )
        )
        == 1
    )


async def test_mountain_message_warns_about_wind_and_frost_in_russian(chat_env, conn):
    headers, chat, trip_id, mday, item, start = await mountain_trip(chat_env, conn)
    await conn.execute("UPDATE chats SET locale = 'ru'")
    deps.configure(weather=FakeWeather(lambda d: weather_day(d, HourWeather(-4.0, 0, 0, 35.0, 3))),
                   router=FakeRouter(), push=FakePush())  # fmt: skip
    clock.set_clock(lambda: at(mday, 7, 5))
    await live_jobs.mountain_notify(
        TransactionalDatabase(conn), {"trip_id": trip_id, "day": mday.isoformat()}
    )
    msg = await fetch_one(
        conn, "SELECT content FROM chat_messages WHERE prompt_id = 'system.mountain.v1'"
    )
    assert "Осторожно" in msg["content"] and "Погода неважная" in msg["content"]


async def test_mountain_notify_retries_when_the_forecast_is_unavailable(chat_env, conn):
    headers, chat, trip_id, mday, item, start = await mountain_trip(chat_env, conn)
    deps.configure(weather=FailingWeather(), router=FakeRouter(), push=FakePush())
    clock.set_clock(lambda: at(mday, 7, 5))
    with pytest.raises(WeatherUnavailable):
        await live_jobs.mountain_notify(
            TransactionalDatabase(conn), {"trip_id": trip_id, "day": mday.isoformat()}
        )
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM trip_day_notices"))["n"] == 0


# --- push delivery ------------------------------------------------------------------------
async def register(client, headers, install, token, language="en"):
    return await client.post(
        "/v1/devices", headers=headers,
        json={"install_id": install, "apns_token": token, "language": language},
    )  # fmt: skip


TOKEN_A, TOKEN_B = "a" * 64, "b" * 64
INSTALL_A, INSTALL_B = (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
)


async def test_push_goes_to_every_device_once_and_dead_tokens_are_forgotten(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    assert (await register(chat_env.client, headers, INSTALL_A, TOKEN_A)).status_code == 200
    assert (await register(chat_env.client, headers, INSTALL_B, TOKEN_B)).status_code == 200
    push = FakePush(invalid={TOKEN_B})
    deps.configure(push=push)
    user = await fetch_one(conn, "SELECT id FROM users")
    from app.live import store as live_store

    nid = await live_store.add_notification(
        conn,
        user["id"],
        "weather_proposal",
        "T",
        "B",
        {"type": "weather_proposal", "trip_id": trip_id, "x": None},
        "k1",
    )
    db = TransactionalDatabase(conn)
    await live_jobs.push_send(db, {"notification_id": str(nid)})
    assert sorted(t for t, _ in push.sent) == [TOKEN_A, TOKEN_B]
    message = push.sent[0][1]
    assert (message.title, message.body) == ("T", "B") and message.data == {
        "type": "weather_proposal",
        "trip_id": trip_id,
    }
    tokens = {
        r["install_id"]: r["apns_token"] for r in await fetch_all(conn, "SELECT * FROM devices")
    }
    assert tokens[__import__("uuid").UUID(INSTALL_B)] is None  # unregistered token dropped
    assert (await fetch_one(conn, "SELECT sent_at FROM push_notifications"))["sent_at"] is not None
    await live_jobs.push_send(db, {"notification_id": str(nid)})
    assert len(push.sent) == 2  # idempotent: nothing is sent twice


async def test_a_failed_device_is_retried_without_repeating_the_served_one(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    await register(chat_env.client, headers, INSTALL_A, TOKEN_A)
    await register(chat_env.client, headers, INSTALL_B, TOKEN_B)

    class Flaky(FakePush):
        down = True

        async def send(self, token, message):
            if token == TOKEN_B and self.down:
                raise PushError("apns 503")
            return await super().send(token, message)

    push = Flaky()
    deps.configure(push=push)
    user = await fetch_one(conn, "SELECT id FROM users")
    from app.live import store as live_store

    nid = await live_store.add_notification(conn, user["id"], "k", "T", "B", {}, "k2")
    db = TransactionalDatabase(conn)
    with pytest.raises(PushError):
        await live_jobs.push_send(db, {"notification_id": str(nid)})
    assert [t for t, _ in push.sent] == [TOKEN_A]
    assert (await fetch_one(conn, "SELECT sent_at FROM push_notifications"))["sent_at"] is None
    push.down = False
    await live_jobs.push_send(db, {"notification_id": str(nid)})
    assert [t for t, _ in push.sent] == [TOKEN_A, TOKEN_B]  # A was not repeated


def test_the_default_push_provider_sends_nothing_and_apns_needs_credentials(monkeypatch):
    from app.config import Settings

    assert isinstance(make_push(Settings(push_provider="log")), LogPushProvider)
    with pytest.raises(PushError, match="credential gap"):
        make_push(Settings(push_provider="apns"))


async def test_apns_adapter_request_format_with_a_mock_transport():
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()  # fmt: skip
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        token = request.url.path.rsplit("/", 1)[1]
        if token == "dead":
            return httpx.Response(410, json={"reason": "Unregistered"})
        if token == "boom":
            return httpx.Response(503, json={"reason": "ServiceUnavailable"})
        return httpx.Response(200)

    now = [1_000_000.0]
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    apns = ApnsProvider("TEAM123456", "KEY1234567", pem, "kz.jol.app", sandbox=True, client=client,
                        clock=lambda: now[0])  # fmt: skip
    ok = await apns.send("abc123", PushMessage("Title", "Body", {"trip_id": "t1"}))
    assert ok.ok
    request = seen[0]
    assert str(request.url) == "https://api.sandbox.push.apple.com/3/device/abc123"
    assert (
        request.headers["apns-topic"] == "kz.jol.app"
        and request.headers["apns-push-type"] == "alert"
    )
    bearer = request.headers["authorization"].split(" ", 1)[1]
    assert jwt.get_unverified_header(bearer) == {"alg": "ES256", "kid": "KEY1234567", "typ": "JWT"}
    claims = jwt.decode(bearer, key.public_key(), algorithms=["ES256"])
    assert claims == {"iss": "TEAM123456", "iat": 1_000_000}
    body = json.loads(request.content)
    assert body["aps"]["alert"] == {"title": "Title", "body": "Body"} and body["trip_id"] == "t1"
    await apns.send("abc123", PushMessage("T", "B"))
    assert seen[1].headers["authorization"] == request.headers["authorization"]  # JWT is reused
    now[0] += 41 * 60
    await apns.send("abc123", PushMessage("T", "B"))
    assert seen[2].headers["authorization"] != request.headers["authorization"]  # and renewed
    dead = await apns.send("dead", PushMessage("T", "B"))
    assert dead.invalid_token and not dead.ok
    with pytest.raises(PushError):
        await apns.send("boom", PushMessage("T", "B"))
    prod = ApnsProvider("T", "K", pem, "kz.jol.app", sandbox=False, client=client)
    await prod.send("zz", PushMessage("T", "B"))
    assert str(seen[-1].url).startswith("https://api.push.apple.com/3/device/")


# --- devices ------------------------------------------------------------------------------
async def test_device_registration_links_the_user_and_moves_tokens(chat_env, conn):
    from tests.test_chat import sign_in

    a = await sign_in(conn, "a@example.com")
    r = await register(chat_env.client, a, INSTALL_A, TOKEN_A, "ru")
    assert r.status_code == 200
    assert r.json() == {"install_id": INSTALL_A, "user_linked": True, "push_enabled": True}
    row = await fetch_one(conn, "SELECT user_id, apns_token, locale FROM devices")
    assert row["apns_token"] == TOKEN_A and row["locale"] == "ru" and row["user_id"] is not None
    # guest call from the same install (signed out): unlinked, no pushes of the previous user
    guest = await chat_env.client.post(
        "/v1/devices", json={"install_id": INSTALL_A, "apns_token": TOKEN_A.upper()}
    )
    assert guest.json() == {"install_id": INSTALL_A, "user_linked": False, "push_enabled": False}
    # a token that moves to another install is taken from the old one
    await register(chat_env.client, a, INSTALL_B, TOKEN_A)
    rows = {
        str(r["install_id"]): r["apns_token"]
        for r in await fetch_all(conn, "SELECT * FROM devices")
    }
    assert rows == {INSTALL_A: None, INSTALL_B: TOKEN_A}
    # validation and auth
    bad = await chat_env.client.post(
        "/v1/devices", json={"install_id": INSTALL_A, "apns_token": "xyz"}
    )
    assert bad.status_code == 422
    junk = await chat_env.client.post("/v1/devices", headers={"Authorization": "Bearer junk"},
                                      json={"install_id": INSTALL_A})  # fmt: skip
    assert junk.status_code == 401


# --- account deletion and merges ----------------------------------------------------------
async def test_deleting_the_user_removes_proposals_notices_and_notifications(chat_env, conn):
    headers, chat, trip_id = await built(chat_env, conn)
    trip = (await get(chat_env, headers, trip_id)).json()
    rainy_day, item = outdoor_item(trip)
    deps.configure(weather=FakeWeather(rainy_on(rainy_day)), router=FakeRouter(), push=FakePush())
    await recheck(TransactionalDatabase(conn), trip_id)
    await conn.execute(
        "INSERT INTO trip_day_notices (trip_id, day, kind) VALUES (%s, %s, 'mountain')",
        (trip_id, rainy_day),
    )
    assert (await chat_env.client.delete("/v1/me", headers=headers)).status_code == 204
    for table in ("trip_change_proposals", "trip_day_notices", "push_notifications", "trips"):
        assert (await fetch_one(conn, "SELECT count(*) AS n FROM %s" % table))["n"] == 0  # noqa: S608
