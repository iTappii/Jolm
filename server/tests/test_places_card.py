"""Ш-70 (server): rating, today's hours and logo on place pins and the place card."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest
from psycopg.types.json import Jsonb

from app.live import clock
from app.places import service
from tests.test_places import add_place

TZ = ZoneInfo("Asia/Almaty")
BBOX = "76.8,43.1,77.1,43.4"
MON, TUE = (2026, 11, 23), (2026, 11, 24)  # 2026-11-23 is a Monday


def at(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


@pytest.fixture
def fake_now():
    def set_(moment):
        clock.set_clock(lambda: moment)

    yield set_
    clock.set_clock(None)


async def add_review(conn, pid, rating, status="published_pending_review"):
    await conn.execute(
        "INSERT INTO submissions (place_id, type, payload, status) VALUES (%s, 'review', %s, %s)",
        (pid, Jsonb({"rating": rating}), status),
    )


async def add_hours(conn, pid, weekday, opens, closes):
    await conn.execute(
        "INSERT INTO place_hours (place_id, weekday, opens, closes) VALUES (%s, %s, %s, %s)",
        (pid, weekday, opens, closes),
    )


async def detail(client, pid):
    return (await client.get("/v1/places/%s" % pid)).json()


async def pin(client, pid):
    items = (await client.get("/v1/places", params={"bbox": BBOX})).json()["items"]
    return next(i for i in items if i["id"] == str(pid))


# ------------------------------------------------------------ today (pure)


def block(hours, moment):
    return service.today_block(hours, moment, TZ)


def test_today_unknown_hours_is_none():
    assert block([], at(*MON, 12)) is None


def test_today_open_now_and_closed_after_hours():
    hours = [(0, time(10), time(23))]
    assert block(hours, at(*MON, 12)) == {
        "opens": "10:00", "closes": "23:00", "open_now": True,
        "open_24h": False, "closed_today": False,
    }  # fmt: skip
    late = block(hours, at(*MON, 23, 30))
    assert late["open_now"] is False and late["closed_today"] is False


def test_today_closed_day():
    hours = [(0, time(10), time(23))]
    assert block(hours, at(*TUE, 12)) == {
        "opens": None, "closes": None, "open_now": False,
        "open_24h": False, "closed_today": True,
    }  # fmt: skip


def test_today_round_the_clock():
    got = block([(0, time(0), time(23, 59))], at(*MON, 3))
    assert got["open_24h"] is True and got["open_now"] is True and got["closed_today"] is False


def test_today_past_midnight_closing():
    hours = [(0, time(20), time(2))]
    evening = block(hours, at(*MON, 23))
    assert (evening["opens"], evening["closes"], evening["open_now"]) == ("20:00", "02:00", True)
    early = block(hours, at(*TUE, 1))  # still open from Monday; Tuesday itself has no hours
    assert early["open_now"] is True and early["closed_today"] is True


def test_today_several_intervals_span_first_to_last():
    got = block([(0, time(14), time(18)), (0, time(9), time(13))], at(*MON, 13, 30))
    assert (got["opens"], got["closes"], got["open_now"]) == ("09:00", "18:00", False)


def test_today_uses_the_given_time_zone_for_the_day():
    from datetime import timezone

    hours = [(0, time(9), time(18))]
    # 2026-11-22 22:00 UTC is Monday 03:00 in Almaty (UTC+5): Monday's hours apply, closed now
    moment = datetime(2026, 11, 22, 22, 0, tzinfo=timezone.utc)
    got = service.today_block(hours, moment, TZ)
    assert got["closed_today"] is False and got["open_now"] is False
    utc = service.today_block(hours, moment, timezone.utc)  # Sunday in UTC: no Sunday hours
    assert utc["closed_today"] is True


def test_region_tz_is_almaty_inside_and_default_outside():
    assert str(service.region_tz(43.25, 76.95)) == "Asia/Almaty"
    assert str(service.region_tz(51.1, 71.4)) == "Asia/Almaty"  # default region fallback


# ------------------------------------------------------------ rating


async def test_rating_null_without_reviews(client, conn):
    pid = await add_place(conn, "Пусто", 76.95, 43.25)
    assert (await detail(client, pid))["rating"] is None
    assert (await pin(client, pid))["rating"] is None


async def test_rating_average_rounds_and_counts_visible_only(client, conn):
    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    other = await add_place(conn, "Другое", 76.96, 43.26)
    for rating, status in [
        (5, "published_pending_review"),  # passed the filter, awaiting a moderator: counts
        (4, "approved"),
        (4, "approved"),
        (1, "rejected"),  # moderator rejected
        (1, "rejected_auto"),  # auto-filter rejected
        (1, "pending_filter"),  # not decided yet
    ]:
        await add_review(conn, pid, rating, status)
    await add_review(conn, other, 1)
    # (5 + 4 + 4) / 3 = 4.333... -> 4.3
    assert (await detail(client, pid))["rating"] == {"average": 4.3, "count": 3}
    assert (await pin(client, pid))["rating"] == {"average": 4.3, "count": 3}
    assert (await pin(client, other))["rating"] == {"average": 1.0, "count": 1}


async def test_rating_rounds_half_up_to_one_decimal(client, conn):
    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    for rating in [5, 4, 4, 5, 5, 4, 5, 5]:  # 37 / 8 = 4.625 -> 4.6
        await add_review(conn, pid, rating)
    assert (await detail(client, pid))["rating"] == {"average": 4.6, "count": 8}


# ------------------------------------------------------------ today (API)


async def test_card_and_pin_today_by_region_time_zone(client, conn, fake_now):
    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    await add_hours(conn, pid, 0, time(10), time(23))
    fake_now(at(*MON, 12))
    expected = {
        "opens": "10:00", "closes": "23:00", "open_now": True,
        "open_24h": False, "closed_today": False,
    }  # fmt: skip
    d = await detail(client, pid)
    assert d["today"] == expected and d["open_now"] is True
    assert (await pin(client, pid))["today"] == expected
    fake_now(at(*TUE, 12))  # no Tuesday hours
    assert (await detail(client, pid))["today"]["closed_today"] is True


async def test_card_today_past_midnight_and_unknown(client, conn, fake_now):
    bar = await add_place(conn, "Бар", 76.95, 43.25)
    await add_hours(conn, bar, 0, time(20), time(2))
    nohours = await add_place(conn, "Без часов", 76.96, 43.26)
    fake_now(at(*MON, 23, 30))
    d = await detail(client, bar)
    assert (d["today"]["closes"], d["today"]["open_now"]) == ("02:00", True)
    assert (await detail(client, nohours))["today"] is None
    assert (await pin(client, nohours))["today"] is None


# ------------------------------------------------------------ address, logo, shapes


async def test_logo_is_null_by_default_and_set_with_source(client, conn, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "media_base_url", "https://media.example")
    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    assert (await detail(client, pid))["logo_url"] is None
    assert (await pin(client, pid))["logo_url"] is None
    await conn.execute(
        "UPDATE places SET logo_key = 'logos/cafe.png', logo_source = 'partner' WHERE id = %s",
        (pid,),
    )
    assert (await detail(client, pid))["logo_url"] == "https://media.example/logos/cafe.png"
    assert (await pin(client, pid))["logo_url"] == "https://media.example/logos/cafe.png"


async def test_logo_needs_a_source(conn):
    import psycopg

    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    with pytest.raises(psycopg.errors.CheckViolation):
        await conn.execute("UPDATE places SET logo_key = 'x.png' WHERE id = %s", (pid,))


async def test_address_on_card_and_pin(client, conn):
    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    bare = await add_place(conn, "Без адреса", 76.96, 43.26)
    await conn.execute(
        "UPDATE places SET address_ru = 'ул. Абая, 10', address_en = 'Abay St 10' WHERE id = %s",
        (pid,),
    )
    ru = {"Accept-Language": "ru"}
    assert (await client.get("/v1/places/%s" % pid, headers=ru)).json()["address"] == "ул. Абая, 10"
    assert (await pin(client, pid))["address"] == "Abay St 10"  # default locale is en
    assert (await detail(client, bare))["address"] is None
    en = (await client.get("/v1/places/%s" % pid, headers={"Accept-Language": "en"})).json()
    assert en["address"] == "Abay St 10"


async def test_pin_and_card_contract_keys(client, conn):
    pid = await add_place(conn, "Кафе", 76.95, 43.25)
    p = await pin(client, pid)
    assert {"rating", "today", "address", "logo_url"} <= set(p)
    d = await detail(client, pid)
    assert {"rating", "today", "address", "logo_url", "open_now"} <= set(d)
