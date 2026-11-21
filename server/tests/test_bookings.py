"""Ш-49. Book from a partner place card and read the request through the public API."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.bookings import adapters, service
from app.config import get_settings
from app.db import fetch_one
from app.live import clock
from tests.test_chat import sign_in
from tests.test_places import add_place

NOW = datetime(2026, 12, 1, tzinfo=timezone.utc)
VISIT = (NOW + timedelta(days=1)).isoformat()
CHECKOUT = (NOW + timedelta(days=3)).isoformat()
URL = "/v1/bookings"


@pytest.fixture(autouse=True)
def booking_settings(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    monkeypatch.setattr(clock, "now", lambda: NOW)


async def link_partner(conn, place, *kinds, adapter="stub", active=True):
    partner = await fetch_one(
        conn,
        "INSERT INTO partners(name, adapter, is_active) VALUES ('Partner', %s, %s) RETURNING id",
        (adapter, active),
    )
    await conn.execute(
        "INSERT INTO partner_places(partner_id, place_id, kinds, external_ref)"
        " VALUES (%s, %s, %s, 'almaty-1')",
        (partner["id"], place, list(kinds)),
    )


@pytest.fixture
async def place(conn):
    return str(await add_place(conn, "Кафе", 76.94, 43.24))


@pytest.mark.parametrize(
    ("kind", "details"),
    [
        ("table", {"starts_at": VISIT, "party_size": 2}),
        ("room", {"starts_at": VISIT, "ends_at": CHECKOUT}),
        ("ticket", {"starts_at": VISIT}),
        ("food", {"note": "No onions"}),
    ],
)
async def test_book_from_card_and_read_confirmation(client, conn, place, kind, details):
    await link_partner(conn, place, kind)
    card = (await client.get("/v1/places/" + place)).json()
    assert card["booking"] == {"available": True, "kinds": [kind]}
    headers = await sign_in(conn)
    response = await client.post(
        URL, headers=headers, json={"place_id": place, "kind": kind, **details}
    )
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    booking = response.json()
    assert booking["status"] == "confirmed" and booking["kind"] == kind
    assert booking["place"] == {"id": place, "name": "Кафе"}
    assert booking["party_size"] == details.get("party_size", 1)
    assert booking["note"] == details.get("note")
    stored = await fetch_one(
        conn, "SELECT external_ref FROM bookings WHERE id = %s", (booking["id"],)
    )
    assert stored["external_ref"] == "stub-" + booking["id"]
    assert (await client.get(URL + "/" + booking["id"], headers=headers)).json() == booking
    assert (await client.get(URL, headers=headers)).json() == {
        "items": [booking],
        "next_cursor": None,
    }


async def test_only_connected_partners_offer_bookings(client, conn, place):
    card_url = "/v1/places/" + place
    data = {"place_id": place, "kind": "food"}
    headers = await sign_in(conn)
    assert (await client.get(card_url)).json()["booking"] is None
    await link_partner(conn, place, "food", active=False)
    await link_partner(conn, place, "food", "ticket", adapter="not-installed")
    assert (await client.get(card_url)).json()["booking"] is None
    response = await client.post(URL, headers=headers, json=data)
    assert (
        response.status_code == 422 and response.json()["error"]["code"] == "booking_not_supported"
    )
    await link_partner(conn, place, "food", "table")
    await link_partner(conn, place, "food", "room")
    assert (await client.get(card_url)).json()["booking"]["kinds"] == ["table", "room", "food"]
    assert (await client.post(URL, headers=headers, json=data)).status_code == 201


async def test_replay_precedes_limits_and_bookings_are_private(client, conn, place, monkeypatch):
    await link_partner(conn, place, "food")
    owner, other = await sign_in(conn), await sign_in(conn, "second@example.com")
    data = {"place_id": place, "kind": "food"}
    assert (await client.post(URL, json=data)).status_code == 401
    assert (await client.get(URL)).status_code == 401
    monkeypatch.setattr(service, "DAILY_LIMIT", 1)
    key = {"Idempotency-Key": "booking-order-1"}
    first = await client.post(URL, headers={**owner, **key}, json=data)
    assert first.status_code == 201, first.text
    replay = await client.post(URL, headers={**owner, **key}, json=data)
    assert replay.status_code == 200 and replay.json() == first.json()
    limited = await client.post(URL, headers=owner, json=data)
    assert limited.status_code == 429 and 0 < int(limited.headers["retry-after"]) <= 86400
    assert (await client.get(URL + "/" + first.json()["id"], headers=other)).status_code == 404
    assert (await client.get(URL, headers=other)).json()["items"] == []
    distinct = await client.post(URL, headers={**other, **key}, json=data)
    assert distinct.status_code == 201 and distinct.json()["id"] != first.json()["id"]


async def test_pagination_at_equal_timestamps(client, conn, place):
    await link_partner(conn, place, "food")
    headers = await sign_in(conn)
    ids = []
    for _ in range(3):
        response = await client.post(URL, headers=headers, json={"place_id": place, "kind": "food"})
        ids.append(response.json()["id"])
    await conn.execute("UPDATE bookings SET created_at = %s", (NOW,))
    first = (await client.get(URL, headers=headers, params={"limit": 2})).json()
    second = (
        await client.get(URL, headers=headers, params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [r["id"] for r in first["items"] + second["items"]] == sorted(ids, reverse=True)
    assert second["next_cursor"] is None
    assert (await client.get(URL + "?cursor=invalid", headers=headers)).status_code == 422


async def test_unavailable_and_invalid_requests_create_no_booking(client, conn, place):
    await link_partner(conn, place, "table", "room", "ticket", "food")
    headers = await sign_in(conn)
    for details in (
        {"kind": "room", "starts_at": VISIT, "ends_at": VISIT},
        {"kind": "table"},
        {"kind": "ticket"},
        {"kind": "food", "event_id": str(uuid4())},
        {"kind": "table", "starts_at": "2000-01-01T12:00:00Z"},
        {"kind": "room", "starts_at": "2026-12-02T10:00:00", "ends_at": CHECKOUT},
    ):
        response = await client.post(URL, headers=headers, json={"place_id": place, **details})
        assert response.status_code == 422, response.text
    too_large = {"place_id": place, "kind": "table", "starts_at": VISIT, "party_size": 11}
    unavailable = await client.post(URL, headers=headers, json=too_large)
    assert (
        unavailable.status_code == 409
        and unavailable.json()["error"]["code"] == "booking_unavailable"
    )
    missing = await client.post(
        URL, headers=headers, json={"place_id": str(uuid4()), "kind": "food"}
    )
    assert missing.status_code == 404
    assert (await client.get(URL, headers=headers)).json()["items"] == []


async def test_event_ticket_requires_a_current_event_at_the_partner_place(client, conn, place):
    await link_partner(conn, place, "ticket")
    other = await add_place(conn, "Другая площадка", 76.96, 43.24)
    headers = await sign_in(conn)
    for venue, start, accepted in (
        (other, NOW + timedelta(days=1), False),
        (place, NOW - timedelta(days=1), False),
        (place, NOW + timedelta(days=1), True),
    ):
        event = await fetch_one(
            conn,
            "INSERT INTO events(place_id, title_ru, starts_at)"
            " VALUES (%s, 'Концерт', %s) RETURNING id",
            (venue, start),
        )
        data = {"place_id": place, "kind": "ticket", "event_id": str(event["id"])}
        response = await client.post(URL, headers=headers, json=data)
        assert response.status_code == (201 if accepted else 422)
        if accepted:
            assert response.json()["event_id"] == data["event_id"]


async def test_pending_booking_refreshes_through_its_adapter(client, conn, place, monkeypatch):
    class Pending(adapters.StubAdapter):
        async def create_booking(self, request):
            assert request.place_ref == "almaty-1"
            return adapters.PartnerResult("pending", "partner-ref")

        async def status(self, external_ref):
            assert external_ref == "partner-ref"
            return "declined"

    monkeypatch.setitem(adapters._ADAPTERS, "pending", Pending())
    await link_partner(conn, place, "food", adapter="pending")
    headers = await sign_in(conn)
    response = await client.post(URL, headers=headers, json={"place_id": place, "kind": "food"})
    assert response.json()["status"] == "pending"
    result = await client.get(URL + "/" + response.json()["id"], headers=headers)
    assert result.json()["status"] == "declined"
    assert (await client.get(URL, headers=headers)).json()["items"] == [result.json()]
