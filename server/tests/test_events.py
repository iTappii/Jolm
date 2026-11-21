"""Ш-48: admin input, dated map pins, venue scoring and event suggestions in chat."""

import json
from datetime import date, datetime, timedelta

import psycopg
import pytest
from merge import merge_place
from pydantic import SecretStr

from app.config import get_settings
from app.db import fetch_one
from app.live import clock
from app.planner.build import build_plan
from app.providers.llm.fake import Step
from app.routing import FakeRouter
from tests.test_admin import logged_in
from tests.test_chat import call, new_chat, sign_in
from tests.test_chat_guest import post, use
from tests.test_places import add_place
from tests.test_trips import brief_call, build, event, seed_world


async def add_event(conn, title, start, end=None, place=None, point=None, promoted=False):
    lon, lat = point or (None, None)
    row = await fetch_one(
        conn,
        """INSERT INTO events (title_ru, starts_at, ends_at, place_id, geom, is_promoted)
           VALUES (%s, %s::timestamptz, %s::timestamptz, %s,
             CASE WHEN %s::float8 IS NOT NULL
                  THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography END, %s)
           RETURNING id""",
        (title, start, end, place, lon, lon, lat, promoted),
    )
    return str(row["id"])


async def test_admin_event_shown_on_localized_map_and_venue_card(client, conn, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: datetime.fromisoformat("2026-12-03T23:55:00+05:00"))
    venue = await add_place(conn, "Клуб", 76.93, 43.22)
    csrf = await logged_in(client, conn)
    form = {
        "title_ru": "Джаз", "title_en": "Jazz", "description_ru": "Квартет",
        "starts_at": "2026-12-04T00:05", "place_id": str(venue), "price_kzt": "3500",
        "sponsor": "Club", "is_promoted": "on", "csrf_token": csrf,
    }  # fmt: skip
    assert (await client.post("/admin/events/new", data=form)).status_code == 303
    url = "/v1/events?from=2026-12-04&to=2026-12-04&bbox=76.9,43.2,77,43.3"
    ru = (await client.get(url, headers={"Accept-Language": "ru"})).json()["items"]
    en = (await client.get(url, headers={"Accept-Language": "en"})).json()["items"]
    assert (
        ru
        == (await client.get(f"/v1/places/{venue}", headers={"Accept-Language": "ru"})).json()[
            "events"
        ]
    )
    assert [(i["title"], i["title_lang"], i["ad_label"]) for i in ru] == [("Джаз", "ru", "Реклама")]
    assert [(i["title"], i["title_lang"], i["ad_label"]) for i in en] == [("Jazz", "en", "Ad")]
    assert en[0]["description"] == "Квартет" and en[0]["is_ad"]
    assert en[0]["place"] == {"id": str(venue), "name": "Клуб"}
    assert (en[0]["lat"], en[0]["lon"]) == pytest.approx((43.22, 76.93))
    assert en[0]["price_kzt"] == 3500 and en[0]["organizer"] == "Club"
    assert en[0]["starts_at"] == "2026-12-04T00:05:00+05:00"
    assert (await client.get("/v1/events?from=2026-12-03&to=2026-12-03")).json()["items"] == []


async def test_map_window_overlap_coordinates_and_hidden_places(client, conn):
    point = (76.94, 43.24)
    hidden = await add_place(conn, "Closed", *point, status="hidden")
    for title, start, end in [
        ("Ended", "2026-12-01T12:00+05:00", "2026-12-03T00:00+05:00"),
        ("Exhibition", "2026-12-02T14:00+05:00", "2026-12-03T10:00+05:00"),
        ("Midnight", "2026-12-03T00:00+05:00", None),
        ("Next day", "2026-12-04T00:00+05:00", None),
    ]:
        await add_event(conn, title, start, end, point=point)
    await add_event(conn, "Outside", "2026-12-03T12:00+05:00", point=(77.0, 43.3))
    await add_event(conn, "No location", "2026-12-03T12:00+05:00")
    await add_event(conn, "Hidden venue", "2026-12-03T12:00+05:00", place=hidden, point=point)
    items = (
        await client.get("/v1/events?from=2026-12-03&to=2026-12-03&bbox=76.93,43.23,76.95,43.25")
    ).json()["items"]
    assert [item["title"] for item in items] == ["Exhibition", "Midnight"]
    assert all(item["place"] is None and item["ad_label"] is None for item in items)
    assert (items[0]["lon"], items[0]["lat"]) == pytest.approx(point)


@pytest.mark.parametrize(
    "query",
    ["from=2026-12-04&to=2026-12-03", "from=2026-01-01&to=2026-03-31", "bbox=0,NaN,1,5"],
)
async def test_map_rejects_invalid_windows_and_boxes(client, query):
    assert (await client.get(f"/v1/events?{query}")).status_code == 422


async def test_public_places_are_ad_free_in_admin_database_and_map(client, conn):
    venue = await add_place(conn, "Музей", 76.92, 43.23)
    # An existing venue can be reclassified after its event was created.
    await add_event(conn, "Выставка", "2026-12-03T11:00+05:00", place=venue, promoted=True)
    await conn.execute("UPDATE places SET is_public = true WHERE id = %s", (venue,))
    csrf = await logged_in(client, conn)
    form = {
        "title_ru": "Акция", "starts_at": "2026-12-04T11:00",
        "place_id": str(venue), "is_promoted": "on", "csrf_token": csrf,
    }  # fmt: skip
    response = await client.post("/admin/events/new", data=form)
    assert response.status_code == 422 and "У достопримечательностей" in response.text
    with pytest.raises(psycopg.errors.CheckViolation):
        async with conn.transaction():
            await add_event(conn, "Bad", "2026-12-04T11:00+05:00", place=venue, promoted=True)
    (item,) = (await client.get("/v1/events?from=2026-12-03&to=2026-12-04")).json()["items"]
    assert item["title"] == "Выставка" and not item["is_ad"] and item["ad_label"] is None


def test_osm_merge_keeps_event_and_removes_promotion_at_public_place(test_db_url):
    with psycopg.connect(test_db_url) as conn, conn.transaction(force_rollback=True):
        make_place = """INSERT INTO places (name_ru, is_public, geom)
                        VALUES ('Зал', %s, ST_SetSRID(ST_MakePoint(76.94,43.24),4326))
                        RETURNING id"""
        keep = conn.execute(make_place, (True,)).fetchone()[0]
        drop = conn.execute(make_place, (False,)).fetchone()[0]
        event_id = conn.execute(
            """INSERT INTO events (title_ru, starts_at, place_id, is_promoted)
               VALUES ('Концерт', now(), %s, true) RETURNING id""",
            (drop,),
        ).fetchone()[0]
        merge_place(conn, keep, drop)
        assert conn.execute(
            "SELECT place_id, is_promoted FROM events WHERE id = %s", (event_id,)
        ).fetchone() == (keep, False)


async def test_planner_and_chat_offer_an_attendable_event_with_its_ad_label(
    chat_env, conn, monkeypatch
):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    await seed_world(conn)
    venue = await fetch_one(conn, "SELECT id FROM places WHERE name_ru = 'Галерея Арт'")
    start = clock.local_today() + timedelta(days=10)
    date_str = start.isoformat()
    show = await add_event(
        conn, "Джаз", date_str + "T10:00+05:00", place=venue["id"], promoted=True
    )
    await add_event(conn, "Ночь", date_str + "T22:00+05:00", place=venue["id"])
    await add_event(
        conn, "Утром", date_str + "T07:00+05:00", date_str + "T10:00+05:00", point=(76.94, 43.24)
    )
    await add_event(
        conn,
        "Позднее",
        (start + timedelta(days=1)).isoformat() + "T11:00+05:00",
        point=(76.94, 43.24),
    )
    router = FakeRouter()
    brief = {
        "start_date": start, "end_date": start, "budget_kzt": 900000,
        "has_accommodation": True, "pace": "calm",
    }  # fmt: skip
    plan = await build_plan(chat_env.app.state.db, brief, router)
    assert [str(row["id"]) for row in plan.selection.events] == [show]
    assert next(c for c in plan.selection.activities if c.place.id == venue["id"]).score.event == 1

    chat_env.app.state.routing_provider = router
    headers = await sign_in(conn, locale="ru")
    chat = await new_chat(chat_env, headers)
    steps = [
        Step(
            tool_calls=[
                brief_call(
                    start_date=date_str, end_date=date_str, has_accommodation=True, pace="calm"
                )
            ]
        ),
        Step(tool_calls=[call("search_events", {"limit": 1})]),
        Step(tool_calls=[call("build_trip", {})]),
    ]
    events, llm = await build(chat_env, headers, chat["id"], steps)
    from_search = json.loads(llm.calls[2].messages[-1].content)["events"]
    from_build = json.loads(llm.calls[3].messages[-1].content)["events"]
    assert from_search == from_build and len(from_search) == 1
    assert (from_search[0]["title"], from_search[0]["ad_label"]) == ("Джаз", "Реклама")
    assert from_search[0]["is_ad"]
    trip_id = event(events, "route_ready")["trip_id"]
    trip = (await chat_env.client.get(f"/v1/trips/{trip_id}", headers=headers)).json()
    assert [item["id"] for item in trip["events"]] == [show]


async def test_map_accepts_last_calendar_day(client):
    assert (await client.get(f"/v1/events?from={date.max}")).json() == {"items": []}


async def test_guest_can_search_evening_events_without_a_trip(chat_env, conn):
    today = clock.local_today().isoformat()
    await add_event(
        conn, "Ночной показ", today + "T23:15+05:00", point=(76.94, 43.24), promoted=True
    )
    llm = use(
        chat_env, steps=[Step(tool_calls=[call("search_events", {})]), Step(text=["Ad: film"])]
    )
    assert (await post(chat_env)).status_code == 200
    result = json.loads(llm.calls[-1].messages[-1].content)
    assert [(row["title"], row["ad_label"]) for row in result["events"]] == [("Ночной показ", "Ad")]
