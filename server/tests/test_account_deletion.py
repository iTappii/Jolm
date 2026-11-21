import json
import logging
import time
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app import worker
from app.auth import apple, apple_grants, email, sms
from app.config import get_settings
from app.db import fetch_all, fetch_one
from tests.conftest import TransactionalDatabase

SUBJECT = "000777.apple-delete.0042"
ADDRESS = {"channel": "email", "destination": "gone@example.com"}
PHONE = {"channel": "phone", "destination": "+7 701 123 45 67"}


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_SECRET", "test-delete-secret-at-least-32-bytes")
    monkeypatch.setenv("APPLE_TEAM_ID", "")
    monkeypatch.setenv("APPLE_KEY_ID", "")
    monkeypatch.setenv("APPLE_PRIVATE_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def delivery(monkeypatch):
    sent = []

    class Capture:
        async def send(self, destination, code):
            sent.append((destination, code))

    monkeypatch.setattr(email, "get_email_provider", lambda: Capture())
    monkeypatch.setattr(sms, "get_sms_provider", lambda: Capture())
    return sent


def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def otp_sign_in(client, delivery, address):
    assert (await client.post("/v1/auth/otp/request", json=address)).status_code == 204
    code = delivery[-1][1]
    response = await client.post("/v1/auth/otp/verify", json={**address, "code": code})
    assert response.status_code == 200, response.text
    return response.json()


async def count(conn, table):
    return (await fetch_one(conn, f"SELECT count(*) AS n FROM {table}"))["n"]  # noqa: S608


async def test_unauthenticated_delete_is_rejected(client):
    assert (await client.delete("/v1/me")).status_code == 401
    bad = await client.delete("/v1/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


async def test_delete_cascades_personal_data_and_kills_tokens(client, conn, delivery):
    tokens = await otp_sign_in(client, delivery, ADDRESS)
    other = await otp_sign_in(client, delivery, {**ADDRESS, "destination": "stays@example.com"})
    user = (await client.get("/v1/me", headers=auth(tokens))).json()
    await conn.execute(
        "INSERT INTO devices(user_id, install_id) VALUES (%s, %s)", (user["id"], uuid4())
    )
    place = await fetch_one(
        conn,
        "INSERT INTO places(name_en, geom) "
        "VALUES ('P', ST_GeogFromText('POINT(76.9 43.2)')) RETURNING id",
    )
    await conn.execute(
        "INSERT INTO place_photos(place_id, storage_key, source, author_user_id) "
        "VALUES (%s, 'k', 'user', %s)",
        (place["id"], user["id"]),
    )
    await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    response = await client.delete("/v1/me", headers=auth(tokens))
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"

    assert await fetch_all(conn, "SELECT subject FROM auth_identities") == [
        {"subject": "stays@example.com"}
    ]
    assert await count(conn, "users") == 1
    assert await count(conn, "sessions") == 1
    assert await count(conn, "devices") == 0
    assert await count(conn, "otp_codes") == 1  # only the other user's code is left
    photo = await fetch_one(conn, "SELECT author_user_id FROM place_photos")
    assert photo == {"author_user_id": None}
    assert (await client.get("/v1/me", headers=auth(tokens))).status_code == 401
    assert (await client.delete("/v1/me", headers=auth(tokens))).status_code == 401
    refresh = await client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401
    assert (await client.get("/v1/me", headers=auth(other))).status_code == 200


async def test_delete_removes_chats_briefs_messages_and_graph(client, conn, delivery):
    tokens = await otp_sign_in(client, delivery, ADDRESS)
    other = await otp_sign_in(client, delivery, {**ADDRESS, "destination": "stays@example.com"})
    chat_ids = []
    for who in (tokens, other):
        chat = (await client.post("/v1/chats", headers=auth(who))).json()
        chat_ids.append(chat["id"])
        await conn.execute(
            "INSERT INTO chat_messages (chat_id, role, content) VALUES (%s, 'user', 'hi')",
            (chat["id"],),
        )
        await conn.execute(
            "INSERT INTO chat_graph_nodes (chat_id, ord, text) VALUES (%s, 1, 'node')",
            (chat["id"],),
        )
        await conn.execute(
            "UPDATE trip_briefs SET budget_kzt = 1000, must_haves = '[\"plov\"]' "
            "WHERE chat_id = %s",
            (chat["id"],),
        )
    for table in ("chats", "trip_briefs", "chat_messages", "chat_graph_nodes"):
        assert await count(conn, table) == 2, table

    assert (await client.delete("/v1/me", headers=auth(tokens))).status_code == 204

    for table in ("chats", "trip_briefs", "chat_messages", "chat_graph_nodes"):
        assert await count(conn, table) == 1, table
    left = await fetch_all(conn, "SELECT id::text AS id FROM chats")
    assert left == [{"id": chat_ids[1]}]
    assert (await client.get("/v1/chats/%s" % chat_ids[1], headers=auth(other))).status_code == 200


async def test_delete_removes_trips_with_items_legs_and_lodging_but_not_places(
    client, conn, delivery
):
    tokens = await otp_sign_in(client, delivery, ADDRESS)
    other = await otp_sign_in(client, delivery, {**ADDRESS, "destination": "stays@example.com"})
    place = (
        await fetch_one(
            conn,
            "INSERT INTO places(name_en, geom) "
            "VALUES ('Shared', ST_GeogFromText('POINT(76.9 43.2)')) RETURNING id",
        )
    )["id"]
    for who in (tokens, other):
        user = (await client.get("/v1/me", headers=auth(who))).json()
        chat = (await client.post("/v1/chats", headers=auth(who))).json()
        trip = (
            await fetch_one(
                conn,
                "INSERT INTO trips (user_id, chat_id, brief, start_date, end_date) "
                "VALUES (%s, %s, '{}', '2026-12-05', '2026-12-05') RETURNING id",
                (user["id"], chat["id"]),
            )
        )["id"]
        items = []
        for ord_ in (1, 2):
            row = await fetch_one(
                conn,
                "INSERT INTO trip_items (trip_id, day, ord, place_id, kind, starts_at, ends_at, "
                "visit_min) VALUES (%s, '2026-12-05', %s, %s, 'activity', "
                "'2026-12-05 10:00+06', '2026-12-05 11:00+06', 60) RETURNING id",
                (trip, ord_, place),
            )
            items.append(row["id"])
        await conn.execute(
            "INSERT INTO trip_legs (trip_id, from_item_id, to_item_id, depart_at, travel_s) "
            "VALUES (%s, %s, %s, '2026-12-05 11:00+06', 300)",
            (trip, items[0], items[1]),
        )
        await conn.execute(
            "INSERT INTO trip_lodging_options (trip_id, place_id, rank, price_per_night_kzt, "
            "nights, total_kzt) VALUES (%s, %s, 1, 5000, 1, 5000)",
            (trip, place),
        )
    for table in ("trips", "trip_items", "trip_legs", "trip_lodging_options"):
        assert await count(conn, table) in (2, 4), table

    assert (await client.delete("/v1/me", headers=auth(tokens))).status_code == 204

    assert await count(conn, "trips") == 1
    assert await count(conn, "trip_items") == 2
    assert await count(conn, "trip_legs") == 1
    assert await count(conn, "trip_lodging_options") == 1
    assert await count(conn, "places") == 1  # the place itself is never deleted with a user


@pytest.mark.parametrize("address", [ADDRESS, PHONE], ids=["email", "phone"])
async def test_same_email_or_phone_can_register_again(client, conn, delivery, address):
    first = await otp_sign_in(client, delivery, address)
    first_id = (await client.get("/v1/me", headers=auth(first))).json()["id"]
    assert (await client.delete("/v1/me", headers=auth(first))).status_code == 204
    second = await otp_sign_in(client, delivery, address)
    me = await client.get("/v1/me", headers=auth(second))
    assert me.status_code == 200 and me.json()["id"] != first_id
    assert (await client.get("/v1/me", headers=auth(first))).status_code == 401


# --- Sign in with Apple ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def ec_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def apple_signin(monkeypatch, rsa_key):
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    public_jwk.update(kid="apple-test-key", use="sig", alg="RS256")

    def get(url, *, timeout):
        return httpx.Response(200, request=httpx.Request("GET", url), json={"keys": [public_jwk]})

    monkeypatch.setattr(apple.httpx, "get", get)
    monkeypatch.setattr(apple, "key_cache", apple.AppleKeyCache())


async def apple_login(client, rsa_key, **body):
    nonce = (await client.post("/v1/auth/apple/challenge")).json()["nonce"]
    token = jwt.encode(
        {
            "iss": "https://appleid.apple.com",
            "aud": "kz.jol.app",
            "sub": SUBJECT,
            "exp": int(time.time()) + 600,
            "nonce": nonce,
        },
        rsa_key,
        algorithm="RS256",
        headers={"kid": "apple-test-key"},
    )
    return await client.post("/v1/auth/apple", json={"identity_token": token, **body})


class FakeGrants:
    def __init__(self, exchange=(SUBJECT, "apple-refresh-1"), fail_revoke=0):
        self.exchange = exchange
        self.fail_revoke = fail_revoke
        self.revoked = []
        self.codes = []

    async def exchange_code(self, code):
        self.codes.append(code)
        if isinstance(self.exchange, Exception):
            raise self.exchange
        return self.exchange

    async def revoke(self, refresh_token):
        if self.fail_revoke:
            self.fail_revoke -= 1
            raise apple_grants.AppleGrantError("Apple revoke returned 500")
        self.revoked.append(refresh_token)


async def test_apple_delete_enqueues_revoke_and_allows_reregistration(
    client, conn, apple_signin, rsa_key, monkeypatch
):
    grants = FakeGrants()
    monkeypatch.setattr(apple_grants, "get_apple_grants", lambda: grants)
    first = await apple_login(client, rsa_key, authorization_code="code-1")
    assert first.status_code == 200 and grants.codes == ["code-1"]
    stored = (await fetch_one(conn, "SELECT provider_refresh_token AS t FROM auth_identities"))["t"]
    assert stored and "apple-refresh-1" not in stored  # encrypted at rest
    assert apple_grants.decrypt_token(stored) == "apple-refresh-1"

    assert (await client.delete("/v1/me", headers=auth(first.json()))).status_code == 204
    assert await count(conn, "auth_identities") == 0
    jobs = await fetch_all(conn, "SELECT kind, payload FROM jobs WHERE kind = 'apple.revoke'")
    assert len(jobs) == 1 and "apple-refresh-1" not in json.dumps(jobs[0]["payload"])

    assert await worker.process_batch(TransactionalDatabase(conn)) >= 1
    assert grants.revoked == ["apple-refresh-1"]
    done = await fetch_one(conn, "SELECT done_at, error FROM jobs WHERE kind = 'apple.revoke'")
    assert done["done_at"] is not None and done["error"] is None

    again = await apple_login(client, rsa_key)
    assert again.status_code == 200
    assert (await client.get("/v1/me", headers=auth(again.json()))).status_code == 200


async def test_failed_revoke_does_not_block_deletion_and_is_retried(
    client, conn, apple_signin, rsa_key, monkeypatch
):
    grants = FakeGrants(fail_revoke=1)
    monkeypatch.setattr(apple_grants, "get_apple_grants", lambda: grants)
    first = await apple_login(client, rsa_key, authorization_code="code-1")
    assert (await client.delete("/v1/me", headers=auth(first.json()))).status_code == 204

    database = TransactionalDatabase(conn)
    await worker.process_batch(database)
    failed = await fetch_one(
        conn, "SELECT attempts, error, done_at FROM jobs WHERE kind='apple.revoke'"
    )
    assert failed["attempts"] == 1 and failed["done_at"] is None
    assert "AppleGrantError" in failed["error"] and grants.revoked == []

    await conn.execute("UPDATE jobs SET run_at = now() WHERE kind = 'apple.revoke'")
    await worker.process_batch(database)
    assert grants.revoked == ["apple-refresh-1"]


async def test_apple_without_stored_token_deletes_and_logs_gap(
    client, conn, apple_signin, rsa_key, caplog
):
    first = await apple_login(client, rsa_key)  # no authorization_code, stub adapter
    with caplog.at_level(logging.WARNING):
        assert (await client.delete("/v1/me", headers=auth(first.json()))).status_code == 204
    assert "apple token not revoked" in caplog.text
    assert await count(conn, "users") == 0
    assert await fetch_all(conn, "SELECT id FROM jobs WHERE kind = 'apple.revoke'") == []


@pytest.mark.parametrize(
    "exchange",
    [apple_grants.AppleGrantError("boom"), ("someone-else", "refresh-x"), None],
    ids=["error", "other-subject", "nothing"],
)
async def test_code_exchange_problems_never_block_sign_in(
    client, conn, apple_signin, rsa_key, monkeypatch, exchange
):
    monkeypatch.setattr(apple_grants, "get_apple_grants", lambda: FakeGrants(exchange=exchange))
    response = await apple_login(client, rsa_key, authorization_code="code-1")
    assert response.status_code == 200
    token = await fetch_one(conn, "SELECT provider_refresh_token AS t FROM auth_identities")
    assert token == {"t": None}


async def test_missing_credentials_adapter_selection(monkeypatch, ec_key):
    assert isinstance(apple_grants.get_apple_grants(), apple_grants.StubAppleGrants)
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    grants = apple_grants.get_apple_grants()
    assert isinstance(grants, apple_grants.MissingCredentialsGrants)
    with pytest.raises(apple_grants.AppleGrantError):
        await grants.revoke("token")
    monkeypatch.setenv("APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setenv("APPLE_KEY_ID", "KEY1234567")
    monkeypatch.setenv("APPLE_PRIVATE_KEY", pem(ec_key))
    get_settings.cache_clear()
    assert isinstance(apple_grants.get_apple_grants(), apple_grants.HttpAppleGrants)


def pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def http_grants(monkeypatch, ec_key, handler):
    monkeypatch.setenv("APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setenv("APPLE_KEY_ID", "KEY1234567")
    # an env var holds the PEM on one line with literal \n
    monkeypatch.setenv("APPLE_PRIVATE_KEY", pem(ec_key).replace("\n", "\\n"))
    get_settings.cache_clear()
    return apple_grants.HttpAppleGrants(get_settings(), httpx.MockTransport(handler))


async def test_http_revoke_request_and_client_secret(monkeypatch, ec_key):
    seen = []

    def handler(request):
        seen.append(
            (str(request.url), {k: v[0] for k, v in parse_qs(request.content.decode()).items()})
        )
        return httpx.Response(200)

    grants = http_grants(monkeypatch, ec_key, handler)
    await grants.revoke("refresh-abc")
    url, form = seen[0]
    assert url == "https://appleid.apple.com/auth/revoke"
    assert form["token"] == "refresh-abc" and form["token_type_hint"] == "refresh_token"
    assert form["client_id"] == "kz.jol.app"
    claims = jwt.decode(
        form["client_secret"],
        ec_key.public_key(),
        algorithms=["ES256"],
        audience="https://appleid.apple.com",
    )
    assert claims["iss"] == "TEAM123456" and claims["sub"] == "kz.jol.app"
    assert claims["exp"] - claims["iat"] == 300
    assert jwt.get_unverified_header(form["client_secret"])["kid"] == "KEY1234567"


@pytest.mark.parametrize(
    ("response", "ok"),
    [
        (httpx.Response(200), True),
        (httpx.Response(400, json={"error": "invalid_grant"}), True),
        (httpx.Response(400, json={"error": "invalid_client"}), False),
        (httpx.Response(500), False),
        (httpx.ConnectTimeout("slow"), False),
    ],
)
async def test_http_revoke_outcomes(monkeypatch, ec_key, response, ok):
    def handler(request):
        if isinstance(response, Exception):
            raise response
        return response

    grants = http_grants(monkeypatch, ec_key, handler)
    if ok:
        await grants.revoke("t")
    else:
        with pytest.raises(apple_grants.AppleGrantError):
            await grants.revoke("t")


async def test_http_exchange_code(monkeypatch, ec_key):
    id_token = jwt.encode({"sub": SUBJECT}, "x" * 32, algorithm="HS256")

    def handler(request):
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        assert str(request.url) == "https://appleid.apple.com/auth/token"
        assert form["grant_type"] == "authorization_code" and form["code"] == "c1"
        return httpx.Response(200, json={"refresh_token": "r1", "id_token": id_token})

    grants = http_grants(monkeypatch, ec_key, handler)
    assert await grants.exchange_code("c1") == (SUBJECT, "r1")
    broken = http_grants(monkeypatch, ec_key, lambda r: httpx.Response(200, json={"x": 1}))
    with pytest.raises(apple_grants.AppleGrantError):
        await broken.exchange_code("c1")


async def test_me_returns_email_and_phone_identities(client, delivery):
    tokens = await otp_sign_in(client, delivery, {**ADDRESS, "destination": "Me@Example.com"})
    me = (await client.get("/v1/me", headers=auth(tokens))).json()
    assert me["email"] == "me@example.com"
    assert me["phone"] is None
    phone = await otp_sign_in(client, delivery, PHONE)
    me = (await client.get("/v1/me", headers=auth(phone))).json()
    assert me["phone"] == "+77011234567"
    assert me["email"] is None
