import logging
import re

import pytest
from pydantic import SecretStr

from app.auth.sms import get_sms_provider, normalize_phone
from app.config import get_settings
from app.errors import AppError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("701 123 45 67", "+77011234567"),
        ("8 (701) 123-45-67", "+77011234567"),
        ("7 701 123 45 67", "+77011234567"),
        (" +7 (701) 123.45.67 ", "+77011234567"),
        ("727 123 45 67", "+77271234567"),
        ("+1 (202) 555-0123", "+12025550123"),
        ("+7 912 123 45 67", "+79121234567"),
    ],
)
def test_normalize_phone(value, expected):
    assert normalize_phone(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "+",
        "+07011234567",
        "+77011234",
        "701123456",
        "8 912 123 45 67",
        "8 (701 123 45 67",
        "+1 202 555 0123 ext 1",
        "+1234567890123456",
        "+７７０１１２３４５６７",
    ],
)
def test_invalid_phone(value):
    with pytest.raises(AppError) as error:
        normalize_phone(value)
    assert (error.value.status_code, error.value.code) == (422, "validation_error")


@pytest.mark.parametrize(
    ("environment", "provider"),
    [("dev", ""), ("test", "unknown"), ("prod", "stub"), ("staging", "stub")],
)
def test_sms_provider_fails_closed(monkeypatch, environment, provider):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", environment)
    monkeypatch.setattr(settings, "sms_provider", provider)
    with pytest.raises(AppError) as error:
        get_sms_provider()
    assert (error.value.status_code, error.value.code) == (503, "otp_delivery_unavailable")


async def test_stub_logs_code_without_destination(monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "sms_provider", "stub")
    with caplog.at_level(logging.INFO, logger="app.auth.sms"):
        await get_sms_provider().send("+77011234567", "123456")
    assert "123456" in caplog.text
    assert "+77011234567" not in caplog.text


async def test_phone_otp_normalizes_identity_and_issues_session(client, conn, monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "sms_provider", "stub")
    monkeypatch.setattr(settings, "auth_secret", SecretStr("fixture-" * 8))

    with caplog.at_level(logging.INFO, logger="app.auth.sms"):
        requested = await client.post(
            "/v1/auth/otp/request", json={"channel": "phone", "destination": "8 (701) 123-45-67"}
        )
    assert requested.status_code == 204
    assert requested.content == b""
    codes = re.findall(r"SMS OTP \(stub\): ([0-9]{6})", caplog.text)
    assert len(codes) == 1

    verification = {"channel": "phone", "destination": "+77011234567", "code": codes[0]}
    verified = await client.post("/v1/auth/otp/verify", json=verification)
    assert verified.status_code == 200
    headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}
    assert (await client.get("/v1/me", headers=headers)).status_code == 200
    identities = await conn.execute("SELECT provider, subject FROM auth_identities")
    identity = await identities.fetchone()
    assert identity == {"provider": "phone", "subject": "+77011234567"}
    assert (await client.post("/v1/auth/otp/verify", json=verification)).status_code == 401


async def test_phone_otp_unavailable_in_production(client, conn, monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "sms_provider", "stub")
    monkeypatch.setattr(settings, "auth_secret", SecretStr("fixture-" * 8))
    with caplog.at_level(logging.INFO, logger="app.auth.sms"):
        response = await client.post(
            "/v1/auth/otp/request", json={"channel": "phone", "destination": "+77011234567"}
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "otp_delivery_unavailable"
    assert "SMS OTP (stub)" not in caplog.text
    assert await (await conn.execute("SELECT count(*) AS n FROM otp_codes")).fetchone() == {"n": 0}
