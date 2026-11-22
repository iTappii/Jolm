"""Ш-55: POST /v1/bookings/{id}/cancel."""

from datetime import timedelta

import pytest
from pydantic import SecretStr

from app.bookings import adapters
from app.config import get_settings
from app.live import clock
from tests.test_bookings import NOW, URL, VISIT, link_partner
from tests.test_chat import sign_in
from tests.test_places import add_place


@pytest.fixture(autouse=True)
def booking_settings(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    monkeypatch.setattr(clock, "now", lambda: NOW)


@pytest.fixture
async def place(conn):
    return str(await add_place(conn, "Кафе", 76.94, 43.24))


async def book(client, headers, place, **details):
    response = await client.post(
        URL, headers=headers, json={"place_id": place, "kind": "table", "party_size": 2, **details}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def cancel(client, headers, booking_id, lang=None):
    h = dict(headers, **({"Accept-Language": lang} if lang else {}))
    return await client.post("%s/%s/cancel" % (URL, booking_id), headers=h)


async def test_cancel_returns_the_booking_as_cancelled(client, conn, place):
    await link_partner(conn, place, "table")
    headers = await sign_in(conn)
    booking = await book(client, headers, place, starts_at=VISIT)
    assert booking["status"] == "confirmed"

    response = await cancel(client, headers, booking["id"])
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "cancelled"
    assert {k: v for k, v in body.items() if k not in ("status", "updated_at")} == {
        k: v for k, v in booking.items() if k not in ("status", "updated_at")
    }  # the same object as GET /v1/bookings/{id}
    assert (await client.get(URL + "/" + booking["id"], headers=headers)).json() == body
    assert (await client.get(URL, headers=headers)).json()["items"] == [body]


async def test_cancel_twice_or_after_start_is_409(client, conn, place, monkeypatch):
    await link_partner(conn, place, "table")
    headers = await sign_in(conn)
    booking = await book(client, headers, place, starts_at=VISIT)
    assert (await cancel(client, headers, booking["id"])).status_code == 200
    again = await cancel(client, headers, booking["id"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_cancellable"
    ru = await cancel(client, headers, booking["id"], "ru")
    assert ru.json()["error"]["message"] == "Эту бронь уже нельзя отменить"

    second = await book(client, headers, place, starts_at=VISIT)  # now the visit has passed
    monkeypatch.setattr(clock, "now", lambda: NOW + timedelta(days=2))
    late = await cancel(client, headers, second["id"])
    assert late.status_code == 409 and late.json()["error"]["code"] == "not_cancellable"
    got = (await client.get(URL + "/" + second["id"], headers=headers)).json()
    assert got["status"] == "confirmed"  # nothing changed


async def test_declined_and_failed_are_not_cancellable(client, conn, place):
    await link_partner(conn, place, "table")
    headers = await sign_in(conn)
    for status in ("declined", "failed"):
        booking = await book(client, headers, place, starts_at=VISIT)
        await conn.execute("UPDATE bookings SET status = %s WHERE id = %s", (status, booking["id"]))
        assert (await cancel(client, headers, booking["id"])).status_code == 409


async def test_pending_booking_can_be_cancelled_and_partner_is_asked(
    client, conn, place, monkeypatch
):
    asked = []

    class Pending(adapters.StubAdapter):
        async def create_booking(self, request):
            return adapters.PartnerResult("pending", "partner-ref")

        async def cancel(self, external_ref):
            asked.append(external_ref)
            return "cancelled"

    monkeypatch.setitem(adapters._ADAPTERS, "pending", Pending())
    await link_partner(conn, place, "table", adapter="pending")
    headers = await sign_in(conn)
    booking = await book(client, headers, place, starts_at=VISIT)
    assert booking["status"] == "pending"
    assert (await cancel(client, headers, booking["id"])).json()["status"] == "cancelled"
    assert asked == ["partner-ref"]


@pytest.mark.parametrize(
    ("outcome", "code", "stays"), [("boom", 503, "confirmed"), ("nope", 409, "confirmed")]
)
async def test_partner_failure_or_refusal_changes_nothing(
    client, conn, place, monkeypatch, outcome, code, stays
):
    class Picky(adapters.StubAdapter):
        async def cancel(self, external_ref):
            if outcome == "boom":
                raise RuntimeError("partner down")
            return "confirmed"  # the partner refuses

    monkeypatch.setitem(adapters._ADAPTERS, "picky", Picky())
    await link_partner(conn, place, "table", adapter="picky")
    headers = await sign_in(conn)
    booking = await book(client, headers, place, starts_at=VISIT)
    response = await cancel(client, headers, booking["id"])
    assert response.status_code == code
    got = (await client.get(URL + "/" + booking["id"], headers=headers)).json()
    assert got["status"] == stays


async def test_cancel_requires_auth_and_hides_foreign_bookings(client, conn, place):
    await link_partner(conn, place, "table")
    headers = await sign_in(conn)
    booking = await book(client, headers, place, starts_at=VISIT)
    assert (await client.post("%s/%s/cancel" % (URL, booking["id"]))).status_code == 401
    other = await sign_in(conn, "b@example.com")
    assert (await cancel(client, other, booking["id"])).status_code == 404
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await cancel(client, headers, unknown)).status_code == 404
    still = (await client.get(URL + "/" + booking["id"], headers=headers)).json()
    assert still["status"] == "confirmed"
