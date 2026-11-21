import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import apple
from app.config import get_settings

SUBJECT = "000123.apple-user.0123"


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def apple_jwks(monkeypatch, private_key):
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update(kid="apple-test-key", use="sig", alg="RS256")
    calls = []

    def get(url, *, timeout):
        calls.append(url)
        assert url == "https://appleid.apple.com/auth/keys"
        assert timeout == 3.0
        return httpx.Response(200, request=httpx.Request("GET", url), json={"keys": [public_jwk]})

    monkeypatch.setattr(apple.httpx, "get", get)
    monkeypatch.setattr(apple, "key_cache", apple.AppleKeyCache())
    monkeypatch.setenv("AUTH_SECRET", "test-apple-auth-key-long-enough-for-hs256")
    get_settings.cache_clear()
    yield calls
    get_settings.cache_clear()


def issue(key, nonce, /, *, kid="apple-test-key", **overrides):
    claims = {
        "iss": "https://appleid.apple.com",
        "aud": "kz.jol.app",
        "sub": SUBJECT,
        "exp": int(time.time()) + 600,
        "nonce": nonce,
        **overrides,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


async def get_nonce(client):
    response = await client.post("/v1/auth/apple/challenge")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["nonce"]


async def submit(client, token):
    return await client.post(
        "/v1/auth/apple", json={"identity_token": token}, headers={"Accept-Language": "ru"}
    )


async def test_valid_signature_replay_and_identity_reuse(client, conn, apple_jwks, private_key):
    nonce = await get_nonce(client)
    token = issue(private_key, nonce, email="relay@privaterelay.appleid.com")
    signed_in = await submit(client, token)
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.headers["cache-control"] == "no-store"
    assert (await submit(client, token)).status_code == 401
    assert (await submit(client, issue(private_key, nonce, sub="other-user"))).status_code == 401

    next_nonce = await get_nonce(client)
    assert next_nonce != nonce
    new_session = await submit(client, issue(private_key, next_nonce))
    assert new_session.status_code == 200, new_session.text
    assert new_session.json()["refresh_token"] != signed_in.json()["refresh_token"]
    identities = await conn.execute(
        """
        SELECT provider, subject, locale FROM auth_identities
        JOIN users ON users.id = auth_identities.user_id
        """
    )
    assert await identities.fetchall() == [
        {"provider": "apple", "subject": SUBJECT, "locale": "ru"}
    ]
    me = await client.get(
        "/v1/me", headers={"Authorization": f"Bearer {new_session.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert len(apple_jwks) == 1


async def test_invalid_signature_does_not_consume_challenge(client, apple_jwks, private_key):
    nonce = await get_nonce(client)
    foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = issue(foreign_key, nonce)
    assert (await submit(client, forged)).status_code == 401
    assert (await submit(client, issue(private_key, nonce))).status_code == 200
    assert len(apple_jwks) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://example.com"},
        {"aud": "com.example.app"},
        {"aud": ["kz.jol.app", "com.example.app"]},
        {"exp": 1},
        {"sub": ""},
        {"nonce": None},
        {"nonce": "not-a-jol-challenge"},
    ],
)
async def test_rejects_invalid_claims(client, apple_jwks, private_key, overrides):
    nonce = await get_nonce(client)
    assert (await submit(client, issue(private_key, nonce, **overrides))).status_code == 401


async def test_rejects_expired_nonce_and_wrong_algorithm_before_fetch(
    client, apple_jwks, private_key, monkeypatch
):
    monkeypatch.setattr(apple, "CHALLENGE_SECONDS", -1)
    expired = await get_nonce(client)
    assert (await submit(client, issue(private_key, expired))).status_code == 401
    algorithm_swap = jwt.encode(
        {"nonce": expired}, b"h" * 32, algorithm="HS256", headers={"kid": "apple-test-key"}
    )
    assert (await submit(client, algorithm_swap)).status_code == 401
    assert apple_jwks == []


async def test_unknown_keys_are_rate_limited(client, apple_jwks, private_key):
    nonce = await get_nonce(client)
    for kid in ("unknown-a", "unknown-b"):
        assert (await submit(client, issue(private_key, nonce, kid=kid))).status_code == 401
    assert (await submit(client, issue(private_key, nonce))).status_code == 200
    assert len(apple_jwks) == 1


async def test_outage_is_rate_limited(client, apple_jwks, private_key, monkeypatch):
    def unavailable(url, *, timeout):
        apple_jwks.append(url)
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(apple.httpx, "get", unavailable)
    token = issue(private_key, await get_nonce(client))
    for _ in range(2):
        response = await submit(client, token)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "auth_unavailable"
    assert len(apple_jwks) == 1
