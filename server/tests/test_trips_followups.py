"""Server follow-ups (2026-11-21): trip title, persisted `late_by_s`, leg path variants,
plan-then-apply edits (`trip_changed`), geometry dedupe of alternatives, `arrive_at` by the
upper estimate."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.db import fetch_one
from app.routing import FakeRouter
from app.routing.base import RouteResult
from app.routing.costs import Tariff
from app.routing.fake import encode_polyline6
from app.routing.service import (
    _distinct_routes,
    get_directions,
    path_distance_m,
)
from app.trips import read, store
from tests.test_trip_edits import pick, post
from tests.test_trips_read import built, get

ROAD = ("walk", "scooter", "taxi", "car")


# --- title ------------------------------------------------------------------------------
def test_trip_title_follows_the_language_and_the_span():
    d = date
    assert read.trip_title(d(2026, 12, 5), d(2026, 12, 7), "ru") == "Алматы, 5–7 дек"
    assert read.trip_title(d(2026, 12, 5), d(2026, 12, 7), "en") == "Almaty, Dec 5–7"
    assert read.trip_title(d(2026, 11, 28), d(2026, 12, 2), "ru") == "Алматы, 28 ноя – 2 дек"
    assert read.trip_title(d(2026, 11, 28), d(2026, 12, 2), "en") == "Almaty, Nov 28 – Dec 2"
    assert read.trip_title(d(2026, 12, 5), d(2026, 12, 5), "ru") == "Алматы, 5 дек"
    assert read.trip_title(d(2026, 12, 5), d(2026, 12, 5), "en") == "Almaty, Dec 5"
    assert read.trip_title(d(2026, 12, 30), d(2027, 1, 2), "en") == (
        "Almaty, Dec 30 2026 – Jan 2 2027"
    )
    assert read.trip_title(d(2026, 12, 5), d(2026, 12, 7), "kk") == "Almaty, Dec 5–7"


async def test_title_is_in_the_list_and_the_trip(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"], "ru")).json()
    start = date.fromisoformat(trip["start_date"])
    end = date.fromisoformat(trip["end_date"])
    assert trip["title"] == read.trip_title(start, end, "ru")
    assert trip["title"].startswith("Алматы, ")
    en = (await get(chat_env, headers, ready["trip_id"], "en")).json()
    assert en["title"] == read.trip_title(start, end, "en")
    listing = await chat_env.client.get(
        "/v1/trips", headers=dict(headers, **{"Accept-Language": "en"})
    )
    assert listing.json()["items"][0]["title"] == en["title"]


# --- late_by_s survives a reload ---------------------------------------------------------
async def test_late_by_s_is_returned_by_get_trip(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    legs = [x for d in trip["days"] for x in d["legs"]]
    assert legs and all(x["late_by_s"] == 0 and x["variant"] == 0 for x in legs)
    leg = legs[0]
    await conn.execute(  # a slow choice: the reserved travel overruns the next stop by an hour
        "UPDATE trip_legs SET travel_s = travel_s + 3600 WHERE id = %s", (leg["id"],)
    )
    again = (await get(chat_env, headers, ready["trip_id"])).json()
    got = next(x for d in again["days"] for x in d["legs"] if x["id"] == leg["id"])
    item = next(i for d in again["days"] for i in d["items"] if i["id"] == leg["to_item_id"])
    arrives = datetime.fromisoformat(got["depart_at"]) + timedelta(seconds=got["travel_s"])
    expected = max(0, int((arrives - datetime.fromisoformat(item["starts_at"])).total_seconds()))
    assert got["late_by_s"] == expected and expected > 0
    others = [x for d in again["days"] for x in d["legs"] if x["id"] != leg["id"]]
    assert all(x["late_by_s"] == 0 for x in others)


async def test_mode_response_and_reload_agree_on_late_by_s(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    leg = next(x for d in trip["days"] for x in d["legs"] if len(x["options"]) > 1)
    slowest = max(
        (o for o in leg["options"] if o["mode"] != leg["chosen_mode"]),
        key=lambda o: o.get("duration_s_max") or o["duration_s"],
    )
    # make the option slower than the gap to the next stop so the warning is non-trivial
    await conn.execute(
        "UPDATE trip_legs SET options = (SELECT jsonb_agg(CASE WHEN o->>'mode' = %s THEN "
        "o || jsonb_build_object('duration_s', 20000, 'duration_s_max', 20000) ELSE o END) "
        "FROM jsonb_array_elements(options) o) WHERE id = %s",
        (slowest["mode"], leg["id"]),
    )
    response = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], leg["id"]),
        headers=headers,
        json={"mode": slowest["mode"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["late_by_s"] > 0 and body["leg"]["late_by_s"] == body["late_by_s"]
    again = (await get(chat_env, headers, ready["trip_id"])).json()
    got = next(x for d in again["days"] for x in d["legs"] if x["id"] == leg["id"])
    assert got["late_by_s"] == body["late_by_s"] and got["variant"] == 0


# --- path variant of a leg ---------------------------------------------------------------
class VariantRouter(FakeRouter):
    """Every road route gets one slower, clearly different alternative."""

    async def routes(self, a, b, mode, alternates=0):
        main = await self.route(a, b, mode)
        # the midpoint pushed sideways by half the segment: a clearly different path
        mid = ((a[0] + b[0]) / 2 - (b[1] - a[1]) / 2, (a[1] + b[1]) / 2 + (b[0] - a[0]) / 2)
        alt = RouteResult(
            mode=mode,
            duration_s=round(main.duration_s * 1.3, 1),
            distance_m=round(main.distance_m * 1.3, 1),
            geometry=encode_polyline6([a, mid, b]),
        )
        return [main, alt]


def road_leg(trip):
    """The longest leg whose chosen mode goes by road (a long leg keeps the variants apart)."""
    legs = [x for d in trip["days"] for x in d["legs"] if x["chosen_mode"] in ROAD]
    assert legs
    return max(
        legs,
        key=lambda x: next(o for o in x["options"] if o["mode"] == x["chosen_mode"])["distance_m"],
    )


async def test_choose_a_path_variant_of_a_leg(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    leg = road_leg(trip)
    mode = leg["chosen_mode"]
    assert {o.get("variant", 0) for o in leg["options"]} == {0}  # the planner keeps variant 0
    chat_env.app.state.routing_provider = VariantRouter()
    url = "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], leg["id"])

    response = await chat_env.client.post(url, headers=headers, json={"mode": mode, "variant": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leg"]["variant"] == 1 and body["leg"]["chosen_mode"] == mode
    chosen = next(o for o in body["leg"]["options"] if o["mode"] == mode and o["variant"] == 1)
    assert body["leg"]["cost_kzt"] == chosen["cost_kzt_max"]
    assert body["leg"]["travel_s"] == round(chosen.get("duration_s_max") or chosen["duration_s"])
    assert body["version"] == 2

    again = (await get(chat_env, headers, ready["trip_id"])).json()
    got = next(x for d in again["days"] for x in d["legs"] if x["id"] == leg["id"])
    assert got["variant"] == 1 and got["travel_s"] == body["leg"]["travel_s"]
    assert [o.get("variant", 0) for o in got["options"] if o["mode"] == mode] == [0, 1]
    assert again["total_cost_kzt"] == body["budget"]["total_kzt"]

    offline = (
        await chat_env.client.get("/v1/trips/%s/offline" % ready["trip_id"], headers=headers)
    ).json()
    off = next(x for d in offline["days"] for x in d["legs"] if x["id"] == leg["id"])
    assert off["variant"] == 1 and off["geometry"] == chosen["geometry"]

    # back to the optimal variant (stored), the answer is idempotent in shape
    back = await chat_env.client.post(url, headers=headers, json={"mode": mode})
    assert back.status_code == 200 and back.json()["leg"]["variant"] == 0
    # a variant nobody offers, a negative one and one too large are refused
    assert (
        await chat_env.client.post(url, headers=headers, json={"mode": mode, "variant": 2})
    ).status_code == 422
    for bad in (-1, 3):
        r = await chat_env.client.post(url, headers=headers, json={"mode": mode, "variant": bad})
        assert r.status_code == 422


async def test_variant_zero_stays_backward_compatible(chat_env, conn):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    leg = next(x for d in trip["days"] for x in d["legs"] if len(x["options"]) > 1)
    other = next(o["mode"] for o in leg["options"] if o["mode"] != leg["chosen_mode"])
    r = await chat_env.client.post(
        "/v1/trips/%s/legs/%s/mode" % (ready["trip_id"], leg["id"]),
        headers=headers,
        json={"mode": other, "variant": 0},
    )
    assert r.status_code == 200 and r.json()["leg"]["variant"] == 0


# --- plan-then-apply (Ш-38 coordinator №1) -----------------------------------------------
class RacingRouter(FakeRouter):
    """Records the order of routing and trip locks; can change the trip while routing."""

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
    log = []
    real = store.get_trip_row

    async def spy(conn, user_id, trip_id, lock=False):
        if lock:
            log.append("lock")
        return await real(conn, user_id, trip_id, lock=lock)

    monkeypatch.setattr(store, "get_trip_row", spy)
    return log


async def test_routing_happens_before_the_trip_is_locked(chat_env, conn, lock_log):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    _, item = pick(trip)
    chat_env.app.state.routing_provider = RacingRouter(conn, lock_log, None)
    lock_log.clear()
    response = await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    assert response.status_code == 200, response.text
    assert lock_log.count("lock") == 1 and "route" in lock_log
    assert lock_log.index("lock") > max(i for i, x in enumerate(lock_log) if x == "route")
    assert response.json()["version"] == 2


async def test_a_trip_changed_while_planning_is_retried_once(chat_env, conn, lock_log):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    day, item = pick(trip)
    router = RacingRouter(conn, lock_log, "once")
    chat_env.app.state.routing_provider = router
    response = await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    assert response.status_code == 200, response.text
    assert router.calls >= 2  # planned twice: the first attempt lost the race
    assert lock_log.count("lock") == 2  # the first one stopped at the version check
    after = (await get(chat_env, headers, ready["trip_id"])).json()
    assert after["version"] == 2  # exactly one applied edit
    assert item["id"] not in [i["id"] for d in after["days"] for i in d["items"]]


async def test_a_trip_that_keeps_changing_answers_409_and_writes_nothing(chat_env, conn, lock_log):
    headers, chat, ready = await built(chat_env, conn)
    trip = (await get(chat_env, headers, ready["trip_id"])).json()
    day, item = pick(trip)
    chat_env.app.state.routing_provider = RacingRouter(conn, lock_log, "always")
    response = await post(chat_env, headers, ready["trip_id"], item["id"], "remove")
    assert response.status_code == 409 and response.json()["error"]["code"] == "trip_changed"
    row = await fetch_one(conn, "SELECT version FROM trips")
    assert row["version"] == 1  # the bumps and every write of both attempts were rolled back
    after = (await get(chat_env, headers, ready["trip_id"])).json()
    assert item["id"] in [i["id"] for d in after["days"] for i in d["items"]]
    signals = await fetch_one(conn, "SELECT count(*) AS n FROM user_place_signals")
    assert signals["n"] == 0


# --- geometry dedupe and arrive_at -------------------------------------------------------
A, B = (43.20, 76.85), (43.26, 76.95)


def route(points, duration=600.0, distance=9000.0):
    return RouteResult(
        mode="car", duration_s=duration, distance_m=distance, geometry=encode_polyline6(points)
    )


def test_path_distance_is_small_for_the_same_streets_and_large_for_a_detour():
    straight = encode_polyline6([A, B])
    shifted = encode_polyline6([(A[0] + 0.0002, A[1]), (B[0] + 0.0002, B[1])])  # about 22 m
    detour = encode_polyline6([A, (43.23 + 0.02, 76.90 - 0.02), B])
    assert path_distance_m(straight, straight) == pytest.approx(0, abs=1)
    assert path_distance_m(straight, shifted) < 40
    assert path_distance_m(straight, detour) > 500
    assert path_distance_m(straight, "not a polyline!!") is None


def test_near_identical_geometry_is_dropped_even_when_time_and_length_differ():
    best = route([A, B], 600, 9000)
    same_streets = route([(A[0] + 0.0002, A[1]), (B[0] + 0.0002, B[1])], 700, 9600)  # +16 %
    detour = route([A, (43.23 + 0.02, 76.90 - 0.02), B], 640, 9800)
    kept = _distinct_routes([best, same_streets, detour])
    assert kept == [best, detour]


async def test_arrive_at_of_motor_modes_uses_the_upper_estimate():
    tariffs = {
        "car": Tariff("car", Decimal(0), Decimal(0), Decimal(75)),
        "scooter": Tariff("scooter", Decimal(100), Decimal(30), Decimal(0)),
    }
    depart = datetime(2026, 11, 23, 3, 0, tzinfo=timezone.utc)  # Monday 08:00 Almaty, peak hour
    options = await get_directions(FakeRouter(), None, tariffs, A, B, depart, variants=1)
    car = next(o for o in options if o.mode == "car")
    assert car.duration_s_max > car.duration_s
    arrive = datetime.fromisoformat(car.arrive_at)
    assert abs(arrive - (depart + timedelta(seconds=car.duration_s_max))) < timedelta(seconds=1)
    scooter = next(o for o in options if o.mode == "scooter")  # no range: the plain duration
    assert scooter.duration_s_max is None
    arrive = datetime.fromisoformat(scooter.arrive_at)
    assert abs(arrive - (depart + timedelta(seconds=scooter.duration_s))) < timedelta(seconds=1)
