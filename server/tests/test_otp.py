import asyncio
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import email, otp
from app.config import get_settings
from app.db import Database, execute, fetch_one
from app.errors import AppError
from app.main import create_app

REQUEST = "/v1/auth/otp/request"
VERIFY = "/v1/auth/otp/verify"
ADDRESS = {"channel": "email", "destination": "User@EXAMPLE.com"}


@pytest.fixture(autouse=True)
def otp_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_SECRET", "test-otp-secret-at-least-32-bytes")
    monkeypatch.setenv("EMAIL_PROVIDER", "stub")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def delivery(monkeypatch):
    class Capture:
        sent = []

        async def send(self, destination, code):
            self.sent.append((destination, code))

    provider = Capture()
    monkeypatch.setattr(email, "get_email_provider", lambda: provider)
    return provider.sent


async def test_email_sign_in_and_replay(client, conn, delivery, monkeypatch):
    monkeypatch.setattr(otp.secrets, "randbelow", lambda _: 12)
    assert (await client.post(REQUEST, json=ADDRESS)).status_code == 204
    assert delivery == [("user@example.com", "000012")]
    stored = await fetch_one(
        conn,
        "SELECT destination_hash, ip_hash, code_hash, expires_at - created_at AS ttl "
        "FROM otp_codes",
    )
    assert stored["ttl"].total_seconds() == 600
    for field in ("destination_hash", "ip_hash", "code_hash"):
        assert len(stored[field]) == 64
    assert "000012" != stored["code_hash"]

    payload = {**ADDRESS, "destination": " user@example.com ", "code": "000012"}
    response = await client.post(VERIFY, json=payload, headers={"Accept-Language": "ru"})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    me = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.json()["locale"] == "ru"
    assert (await client.post(VERIFY, json=payload)).status_code == 401


@pytest.mark.parametrize("expiry", [False, True])
async def test_email_code_expiry_and_failed_attempts(client, conn, delivery, expiry):
    assert (await client.post(REQUEST, json=ADDRESS)).status_code == 204
    code = delivery[0][1]
    if expiry:
        await execute(conn, "UPDATE otp_codes SET expires_at = clock_timestamp()")
    else:
        wrong = f"{(int(code) + 1) % 1_000_000:06d}"
        for _ in range(5):
            assert (await client.post(VERIFY, json={**ADDRESS, "code": wrong})).status_code == 401
    assert (await client.post(VERIFY, json={**ADDRESS, "code": code})).status_code == 401
    row = await fetch_one(conn, "SELECT attempts FROM otp_codes")
    assert row["attempts"] == (0 if expiry else 5)


async def test_email_destination_limit_and_resend(client, conn, delivery, monkeypatch):
    numbers = iter(range(1, otp.DESTINATION_LIMIT + 2))
    monkeypatch.setattr(otp.secrets, "randbelow", lambda _: next(numbers))
    for _ in range(otp.DESTINATION_LIMIT):
        assert (await client.post(REQUEST, json=ADDRESS)).status_code == 204
    response = await client.post(REQUEST, json={**ADDRESS, "destination": "user@example.com"})
    assert response.status_code == 429
    assert len(delivery) == otp.DESTINATION_LIMIT
    for _, code in delivery[:-1]:
        assert (await client.post(VERIFY, json={**ADDRESS, "code": code})).status_code == 401
    assert (await client.post(VERIFY, json={**ADDRESS, "code": delivery[-1][1]})).status_code == 200


async def test_ip_limit_shared_across_destinations_and_forwarded_headers(client, conn, delivery):
    for count in range(otp.IP_LIMIT + 1):
        destination = {**ADDRESS, "destination": f"user{count}@example.com"}
        headers = {"X-Forwarded-For": f"192.0.2.{count + 1}"}
        response = await client.post(REQUEST, json=destination, headers=headers)
        assert response.status_code == (204 if count < otp.IP_LIMIT else 429)
    await execute(conn, "UPDATE otp_codes SET created_at = now() - interval '11 minutes'")
    assert (await client.post(REQUEST, json=destination)).status_code == 204


async def test_failed_delivery_spends_rate_slot_and_keeps_code_inactive(client, conn, monkeypatch):
    class BrokenProvider:
        async def send(self, destination, code):
            raise AppError(503, "otp_delivery_unavailable")

    monkeypatch.setattr(email, "get_email_provider", BrokenProvider)
    monkeypatch.setattr(otp.secrets, "randbelow", lambda _: 42)
    for _ in range(otp.DESTINATION_LIMIT):
        response = await client.post(REQUEST, json=ADDRESS)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "otp_delivery_unavailable"
    assert (await client.post(REQUEST, json=ADDRESS)).status_code == 429
    assert (await client.post(VERIFY, json={**ADDRESS, "code": "000042"})).status_code == 401
    row = await fetch_one(conn, "SELECT count(*) AS total FROM otp_codes")
    assert row["total"] == otp.DESTINATION_LIMIT


async def test_invalid_email_never_delivers(client, delivery):
    response = await client.post(REQUEST, json={**ADDRESS, "destination": "Name <x@example.com>"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "otp_invalid_destination"
    assert delivery == []


async def test_concurrent_email_send_limit_and_consume_once(
    committed_auth_db_url, delivery, monkeypatch
):
    monkeypatch.setattr(otp.secrets, "randbelow", lambda _: 24)
    app = create_app()
    db = Database(committed_auth_db_url, min_size=1, max_size=6)
    app.state.db = db
    await db.open()
    try:
        transport = ASGITransport(app=app, client=("192.0.2.200", 2100))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            address = {**ADDRESS, "destination": "concurrent@example.com"}
            requests = await asyncio.gather(
                *(client.post(REQUEST, json=address) for _ in range(otp.DESTINATION_LIMIT + 2))
            )
            assert sorted(response.status_code for response in requests) == [
                204,
                204,
                204,
                429,
                429,
            ]
            payload = {**address, "code": delivery[-1][1]}
            responses = await asyncio.gather(*(client.post(VERIFY, json=payload) for _ in range(2)))
            assert sorted(response.status_code for response in responses) == [200, 401]
    finally:
        await db.close()


async def test_pending_delivery_does_not_hold_database_transaction(
    committed_auth_db_url, monkeypatch
):
    started = asyncio.Event()
    release = asyncio.Event()
    codes = iter([31, 42])
    monkeypatch.setattr(otp.secrets, "randbelow", lambda _: next(codes))

    class DelayedProvider:
        async def send(self, destination, code):
            if code == "000031":
                started.set()
                await release.wait()

    monkeypatch.setattr(email, "get_email_provider", DelayedProvider)
    app = create_app()
    db = Database(committed_auth_db_url, min_size=1, max_size=1)
    app.state.db = db
    await db.open()
    try:
        transport = ASGITransport(app=app, client=("192.0.2.201", 2100))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            address = {**ADDRESS, "destination": "pending@example.com"}
            first = asyncio.create_task(client.post(REQUEST, json=address))
            try:
                await asyncio.wait_for(started.wait(), timeout=5)
                verify = client.post(VERIFY, json={**address, "code": "000031"})
                assert (await asyncio.wait_for(verify, timeout=5)).status_code == 401
                resend = client.post(REQUEST, json=address)
                assert (await asyncio.wait_for(resend, timeout=5)).status_code == 204
            finally:
                release.set()
                assert (await first).status_code == 204
            assert (
                await client.post(VERIFY, json={**address, "code": "000031"})
            ).status_code == 401
            assert (
                await client.post(VERIFY, json={**address, "code": "000042"})
            ).status_code == 200
    finally:
        await db.close()


@pytest.mark.parametrize("tls", ["starttls", "implicit"])
async def test_smtp_adapter_requires_tls_before_credentials_and_send(monkeypatch, tls):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SMTP_HOST", "relay.example.com")
    monkeypatch.setenv("SMTP_FROM", "auth@example.com")
    monkeypatch.setenv("SMTP_USERNAME", "login")
    monkeypatch.setenv("SMTP_PASSWORD", "password")
    monkeypatch.setenv("SMTP_TLS", tls)
    connection = Mock()
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=None)
    connection.return_value = client
    forbidden = "SMTP_SSL" if tls == "starttls" else "SMTP"
    constructor = "SMTP" if tls == "starttls" else "SMTP_SSL"
    monkeypatch.setattr(email.smtplib, constructor, connection)
    monkeypatch.setattr(email.smtplib, forbidden, Mock(side_effect=AssertionError))
    await email.get_email_provider().send("user@example.com", "012345")
    transport_context = (
        client.starttls.call_args.kwargs["context"]
        if tls == "starttls"
        else connection.call_args.kwargs["context"]
    )
    assert transport_context.check_hostname
    methods = [call[0] for call in client.method_calls]
    assert methods == (["starttls"] if tls == "starttls" else []) + ["login", "send_message"]
    client.login.assert_called_once_with("login", "password")
    message = client.send_message.call_args.args[0]
    assert message["To"] == "user@example.com"
    assert "012345" in message.get_content()
    client.send_message.side_effect = email.smtplib.SMTPRecipientsRefused({})
    with pytest.raises(AppError) as exc:
        await email.get_email_provider().send("user@example.com", "012345")
    assert exc.value.code == "otp_delivery_unavailable"


def test_email_dev_stub_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(AppError) as exc:
        email.get_email_provider()
    assert exc.value.code == "otp_delivery_unavailable"
