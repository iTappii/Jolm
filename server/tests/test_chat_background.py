"""The live route is built in the background and the chat does not wait for it (Ш-64)."""

import asyncio
import json
import logging
from types import SimpleNamespace

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from pydantic import SecretStr

from app.auth import sessions
from app.chat import api as chat_api
from app.chat import events_bus, live_route
from app.config import get_settings
from app.db import Database, fetch_one
from app.main import create_app
from app.providers.llm import FakeLLM
from app.providers.llm.fake import Step
from app.routing import FakeRouter
from tests.conftest import parse_sse
from tests.test_chat import call, say, use
from tests.test_live_route import BAZAAR, CHINESE, PARK, RACE_PLACES, SUSHI, seed, world  # noqa: F401
from tests.test_places import add_place, load_categories


@pytest.fixture(autouse=True)
def signing_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))


class GateRouter(FakeRouter):
    """Routes wait until the gate opens, so a test decides when the background pass can end."""

    def __init__(self) -> None:
        super().__init__()
        self.gate = asyncio.Event()
        self.calls = 0

    async def route(self, from_point, to_point, mode):
        self.calls += 1
        await self.gate.wait()
        return await super().route(from_point, to_point, mode)


class SlowRouter(FakeRouter):
    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay

    async def route(self, from_point, to_point, mode):
        await asyncio.sleep(self.delay)
        return await super().route(from_point, to_point, mode)


@pytest.fixture
async def bg(committed_auth_db_url):
    """Real pool on a committed database (a background task and a request really overlap, and
    NOTIFY really reaches a LISTEN connection)."""
    async with await AsyncConnection.connect(
        committed_auth_db_url, autocommit=True, row_factory=dict_row
    ) as setup:
        await load_categories(setup)
        for name, lon, lat, cat, pop in RACE_PLACES:
            await add_place(setup, name, lon, lat, cat, "active", pop)
        tokens = await sessions.sign_in(setup, "email", "bg@example.com", "en")
        chat = await fetch_one(
            setup,
            "INSERT INTO chats (user_id, locale) SELECT id, 'en' FROM users LIMIT 1 RETURNING id",
        )
        await setup.execute("INSERT INTO trip_briefs (chat_id) VALUES (%s)", (chat["id"],))
    app = create_app()
    db = Database(committed_auth_db_url, min_size=1, max_size=8)
    app.state.db = db
    app.state.listen_url = committed_auth_db_url
    app.state.routing_provider = FakeRouter()
    await db.open()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(
            app=app,
            db=db,
            client=client,
            url=committed_auth_db_url,
            chat_id=chat["id"],
            headers={"Authorization": "Bearer %s" % tokens.access_token},
            scheduler=chat_api.scheduler_of(app),
            bus=chat_api.bus_of(app),
        )
    for name in ("live_routes", "chat_event_bus"):
        part = getattr(app.state, name, None)
        if part is not None:
            await part.close()
    await db.close()
    async with await AsyncConnection.connect(committed_auth_db_url, autocommit=True) as cleanup:
        await cleanup.execute("TRUNCATE places, place_categories, rate_limit_hits CASCADE")


def wishes_call(*wishes):
    return call("update_trip_brief", {"must_haves": list(wishes)})


async def send(bg, *tool_calls, steps=None):
    """One chat turn whose first model round makes `tool_calls`; returns the parsed stream."""
    use(
        SimpleNamespace(app=bg.app),
        steps=steps or [Step(tool_calls=list(tool_calls)), Step(text=["ok"])],
    )
    response = await say(SimpleNamespace(client=bg.client), bg.headers, bg.chat_id)
    assert response.status_code == 200, response.text
    return parse_sse(response.text)


async def stored(bg):
    async with bg.db.transaction() as conn:
        return await live_route.load(conn, bg.chat_id, "en")


async def kinds_until(queue, wanted, timeout=5.0):
    """Event kinds from a bus queue until `wanted` arrived."""
    seen = []
    while wanted not in seen:
        seen.append(await asyncio.wait_for(queue.get(), timeout))
    return seen


# --- the chat does not wait for the map ---------------------------------------------------------


async def test_text_comes_before_the_route_and_done_does_not_wait_for_it(bg):
    router = bg.app.state.routing_provider = GateRouter()
    async with bg.bus.subscribe(bg.chat_id) as queue:
        events = await send(bg, wishes_call(CHINESE, PARK))
        names = [n for n, _ in events]
        # the router is blocked, yet the whole turn (text and `done`) is over
        assert names[:2] == ["brief_updated", "live_route_status"]
        assert events[1][1] == {"state": "building"}
        assert "text_delta" in names and names[-1] == "done"
        assert "live_route" not in names
        assert bg.scheduler.is_building(bg.chat_id)
        assert await stored(bg) is None
        # the lease is free: the next message is accepted while the map is still being built
        again = await send(bg, steps=[Step(text=["still here"])])
        assert again[-1][0] == "done"

        router.gate.set()
        await bg.scheduler.drain()
        assert not bg.scheduler.is_building(bg.chat_id)
        route = await stored(bg)
        assert [s["wish"] for s in route["stops"]] == [CHINESE, PARK]
        assert await kinds_until(queue, "live_route") == ["building", "live_route"]


async def test_tool_result_tells_the_model_the_map_is_building(bg):
    bg.app.state.routing_provider = GateRouter()
    llm = FakeLLM(steps=[Step(tool_calls=[wishes_call(CHINESE, PARK)]), Step(text=["ok"])])
    bg.app.state.llm_provider = llm
    await say(SimpleNamespace(client=bg.client), bg.headers, bg.chat_id)
    result = json.loads([m for m in llm.calls[1].messages if m.role == "tool"][0].content)
    assert result["live_route"] == "building"
    assert "stops" not in result and "legs" not in result
    bg.app.state.routing_provider.gate.set()
    await bg.scheduler.drain()


async def test_a_pass_that_ends_before_done_is_announced_in_the_message_stream(bg):
    bg.app.state.routing_provider = FakeRouter()  # instant
    slow_text = Step(text=["ok"], delay_sec=0.4)  # the model is slower than the map
    events = await send(bg, steps=[Step(tool_calls=[wishes_call(CHINESE, PARK)]), slow_text])
    names = [n for n, _ in events]
    assert names[-4:] == ["map_places", "live_route", "live_route_status", "done"]
    route = [d for n, d in events if n == "live_route"][0]
    assert [s["wish"] for s in route["stops"]] == [CHINESE, PARK]
    assert events[-2][1] == {"state": "ready"}
    await bg.scheduler.drain()


async def test_turn_timing_is_logged_without_text(bg, caplog):
    caplog.set_level(logging.INFO)
    await send(bg, wishes_call(CHINESE))
    await bg.scheduler.drain()
    rows = [r for r in caplog.records if r.getMessage() == "chat turn timing"]
    assert len(rows) == 1
    row = rows[0]
    assert len(row.llm_rounds_ms) == 2 and row.first_text_ms is not None
    assert [t["name"] for t in row.tools_ms] == ["update_trip_brief"]
    assert "total_ms" in row.__dict__
    runner = [r for r in caplog.records if r.getMessage() == "live route runner"]
    assert runner and runner[0].passes == 1 and "total_ms" in runner[0].__dict__
    assert any(
        r.getMessage() == "live route pass" and hasattr(r, "sync_ms") for r in caplog.records
    )


# --- races --------------------------------------------------------------------------------------


async def test_messages_during_a_pass_cost_one_extra_pass_and_the_latest_wins(bg):
    router = bg.app.state.routing_provider = GateRouter()
    await send(bg, wishes_call(CHINESE, PARK))  # pass 1 starts and blocks on the router
    for _ in range(100):
        if router.calls:
            break
        await asyncio.sleep(0.02)
    assert router.calls and bg.scheduler.is_building(bg.chat_id)
    await send(bg, wishes_call(SUSHI))
    await send(bg, wishes_call(BAZAAR))  # two more changes while pass 1 has not ended
    router.gate.set()
    await bg.scheduler.drain()

    assert bg.scheduler.passes == 2  # the first one, and exactly one more (not one per request)
    route = await stored(bg)
    assert [s["wish"] for s in route["stops"]] == [CHINESE, PARK, SUSHI, BAZAAR]
    async with bg.db.transaction() as conn:
        brief = await fetch_one(
            conn, "SELECT must_haves FROM trip_briefs WHERE chat_id = %s", (bg.chat_id,)
        )
    assert brief["must_haves"] == [CHINESE, PARK, SUSHI, BAZAAR]


async def test_the_pass_reads_the_latest_brief_not_a_captured_list(bg):
    router = bg.app.state.routing_provider = GateRouter()
    seen = []
    original = live_route.sync

    async def spy(db, chat_id, locale, router_, wishes):
        seen.append(list(wishes))
        return await original(db, chat_id, locale, router_, wishes)

    live_route.sync = spy
    try:
        await send(bg, wishes_call(CHINESE, PARK))
        await send(bg, wishes_call(SUSHI))
        router.gate.set()
        await bg.scheduler.drain()
    finally:
        live_route.sync = original
    assert seen[0] == [CHINESE, PARK] or seen[0] == [CHINESE, PARK, SUSHI]
    assert seen[-1] == [CHINESE, PARK, SUSHI]


async def test_failed_pass_leaves_the_route_and_says_failed(bg, monkeypatch):
    await send(bg, wishes_call(CHINESE))
    await bg.scheduler.drain()
    before = await stored(bg)
    assert before is not None

    async def boom(*args, **kwargs):
        raise RuntimeError("router exploded")

    original = live_route.sync
    monkeypatch.setattr(live_route, "sync", boom)
    async with bg.bus.subscribe(bg.chat_id) as queue:
        events = await send(bg, wishes_call(CHINESE, PARK))
        assert [n for n, _ in events][:2] == ["brief_updated", "live_route_status"]
        await bg.scheduler.drain()
        assert await kinds_until(queue, "failed") == ["building", "failed"]
    assert await stored(bg) == before
    assert not bg.scheduler.is_building(bg.chat_id)  # and the chat can build again
    monkeypatch.setattr(live_route, "sync", original)
    await send(bg, wishes_call(SUSHI))
    await bg.scheduler.drain()
    assert [s["wish"] for s in (await stored(bg))["stops"]] == [CHINESE, PARK, SUSHI]


async def test_shutdown_cancels_a_running_pass_cleanly(bg):
    bg.app.state.routing_provider = GateRouter()
    await send(bg, wishes_call(CHINESE, PARK))
    for _ in range(100):
        if bg.app.state.routing_provider.calls:
            break
        await asyncio.sleep(0.02)
    await bg.scheduler.close()
    assert not bg.scheduler.is_building(bg.chat_id)
    assert await stored(bg) is None  # nothing half-written


async def test_choose_notifies_other_subscribers(bg):
    await send(bg, wishes_call(CHINESE, PARK))
    await bg.scheduler.drain()
    route = await stored(bg)
    alt = route["stops"][0]["alternatives"][0]["id"]
    async with bg.bus.subscribe(bg.chat_id) as queue:
        response = await bg.client.post(
            "/v1/chats/%s/live-route/choose" % bg.chat_id,
            headers=bg.headers,
            json={"ord": 1, "place_id": alt},
        )
        assert response.status_code == 200, response.text
        assert await kinds_until(queue, "live_route") == ["live_route"]


# --- the events endpoint ------------------------------------------------------------------------


def parse_stream(text):
    """(events, keepalive_count) of a text/event-stream body that may contain comments."""
    events, keepalives = [], 0
    for block in text.split("\n\n"):
        if block == ": keepalive":
            keepalives += 1
        elif block:
            name, data = block.split("\n")
            events.append((name[len("event: ") :], json.loads(data[len("data: ") :])))
    return events, keepalives


async def notify(url, chat_id, kind, delay=0.0):
    await asyncio.sleep(delay)
    async with await AsyncConnection.connect(url, autocommit=True) as conn:
        await conn.execute(
            "SELECT pg_notify(%s, %s)",
            (events_bus.CHANNEL, json.dumps({"chat": str(chat_id), "kind": kind})),
        )


@pytest.fixture
def short_streams(monkeypatch):
    monkeypatch.setattr(chat_api, "EVENTS_MAX_SEC", 1.4)
    monkeypatch.setattr(chat_api, "EVENTS_KEEPALIVE_SEC", 0.4)


async def get_events(client, chat_id, headers):
    return await client.get("/v1/chats/%s/events" % chat_id, headers=headers)


async def test_events_endpoint_needs_the_owner(bg, short_streams):
    other = await bg.client.post("/v1/chats", headers=bg.headers)
    assert other.status_code == 201
    assert (await get_events(bg.client, bg.chat_id, {})).status_code == 401
    bad = await get_events(bg.client, bg.chat_id, {"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    async with bg.db.transaction() as conn:
        stranger = await sessions.sign_in(conn, "email", "stranger@example.com", "en")
    theirs = {"Authorization": "Bearer %s" % stranger.access_token}
    assert (await get_events(bg.client, bg.chat_id, theirs)).status_code == 404
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await get_events(bg.client, unknown, bg.headers)).status_code == 404


async def test_events_snapshot_updates_after_notify_and_keepalive(bg, short_streams):
    await send(bg, wishes_call(CHINESE, PARK))
    await bg.scheduler.drain()
    route = await stored(bg)

    pusher = asyncio.ensure_future(notify(bg.url, bg.chat_id, "live_route", delay=0.6))
    response = await get_events(bg.client, bg.chat_id, bg.headers)
    await pusher
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events, keepalives = parse_stream(response.text)
    assert [n for n, _ in events] == [
        "live_route", "live_route_status", "live_route", "live_route_status"
    ]  # fmt: skip
    assert events[0][1] == route and events[2][1] == route
    assert events[1][1] == events[3][1] == {"state": "ready"}
    assert keepalives >= 1


async def test_events_snapshot_of_an_empty_chat_and_of_a_running_pass(
    bg, short_streams, monkeypatch
):
    first = await get_events(bg.client, bg.chat_id, bg.headers)
    events, _ = parse_stream(first.text)
    assert events == [
        ("live_route", {"stops": [], "legs": []}),
        ("live_route_status", {"state": "ready"}),
    ]

    gate = asyncio.Event()

    async def blocked(*args, **kwargs):
        await gate.wait()
        return None, False, {}

    monkeypatch.setattr(live_route, "sync", blocked)
    bg.scheduler.schedule(bg.db, bg.chat_id, "en", FakeRouter())
    await asyncio.sleep(0.1)
    building, _ = parse_stream((await get_events(bg.client, bg.chat_id, bg.headers)).text)
    assert building[1] == ("live_route_status", {"state": "building"})
    gate.set()
    await bg.scheduler.drain()


async def test_events_stream_relays_building_and_failed_kinds(bg, short_streams):
    pushes = asyncio.gather(
        notify(bg.url, bg.chat_id, "building", 0.5), notify(bg.url, bg.chat_id, "failed", 0.8)
    )
    events, _ = parse_stream((await get_events(bg.client, bg.chat_id, bg.headers)).text)
    await pushes
    assert [d["state"] for n, d in events if n == "live_route_status"] == [
        "ready",
        "building",
        "failed",
    ]
    # nothing about other chats leaks in
    other = "11111111-1111-1111-1111-111111111111"
    pusher = asyncio.ensure_future(notify(bg.url, other, "live_route", 0.5))
    events, _ = parse_stream((await get_events(bg.client, bg.chat_id, bg.headers)).text)
    await pusher
    assert len(events) == 2


async def test_all_clients_share_one_listen_connection(bg, short_streams, monkeypatch):
    connects = []
    real = psycopg.AsyncConnection.connect.__func__

    async def counting(cls, *args, **kwargs):
        if kwargs.get("autocommit"):  # the pool's own connections are not autocommit
            connects.append(1)
        return await real(cls, *args, **kwargs)

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", classmethod(counting))
    await asyncio.gather(*(get_events(bg.client, bg.chat_id, bg.headers) for _ in range(3)))
    assert len(connects) == 1


# --- legs are computed concurrently -------------------------------------------------------------


async def test_legs_are_computed_concurrently_with_the_same_result(conn, monkeypatch):
    from tests.conftest import TransactionalDatabase

    ids = await seed(conn)
    order = list(ids.values())
    places = {}
    for pid, (_, lon, lat, _, _) in zip(
        order, __import__("tests.test_live_route", fromlist=["PLACES"]).PLACES
    ):
        places[pid] = {"lat": lat, "lon": lon}
    db = TransactionalDatabase(conn)
    router = FakeRouter()

    def stops():
        return [live_route.Stop("w%d" % i, pid, []) for i, pid in enumerate(order)]

    state = {"now": 0, "max": 0}
    original = live_route.compute_leg

    async def tracked(*args):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        try:
            await asyncio.sleep(0.05)
            return await original(*args)
        finally:
            state["now"] -= 1

    monkeypatch.setattr(live_route, "compute_leg", tracked)
    fast = stops()
    await live_route._fill_legs(db, router, fast, places, [])
    assert 1 < state["max"] <= live_route.LEG_CONCURRENCY

    monkeypatch.setattr(live_route, "LEG_CONCURRENCY", 1)  # one by one: the old behaviour
    state["max"] = 0
    one_by_one = stops()
    await live_route._fill_legs(db, router, one_by_one, places, [])
    assert state["max"] == 1
    assert [s.leg for s in fast] == [s.leg for s in one_by_one]
    assert fast[0].leg is None and all(s.leg for s in fast[1:])


async def test_known_legs_are_reused_and_not_computed_again(conn, monkeypatch):
    from tests.conftest import TransactionalDatabase
    from tests.test_live_route import PLACES

    ids = await seed(conn)
    order = list(ids.values())[:3]
    places = {pid: {"lat": p[2], "lon": p[1]} for pid, p in zip(order, PLACES)}
    db = TransactionalDatabase(conn)
    first = [live_route.Stop("w%d" % i, pid, []) for i, pid in enumerate(order)]
    await live_route._fill_legs(db, FakeRouter(), first, places, [])
    calls = []
    original = live_route.compute_leg

    async def spy(*args):
        calls.append(args[2:4])
        return await original(*args)

    monkeypatch.setattr(live_route, "compute_leg", spy)
    again = [live_route.Stop("w%d" % i, pid, []) for i, pid in enumerate(order)]
    await live_route._fill_legs(db, FakeRouter(), again, places, first)
    assert calls == [] and [s.leg for s in again] == [s.leg for s in first]
