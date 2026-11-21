import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import psycopg
import pytest
from psycopg.rows import dict_row
from pydantic import SecretStr

from app.auth import sessions
from app.config import get_settings
from app.errors import AppError


@pytest.fixture(autouse=True)
def signing_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))


async def test_issue_refresh_revoke(client, conn):
    first = await sessions.sign_in(conn, "email", "reader@example.org", "ru")
    claims = jwt.decode(
        first.access_token,
        sessions.signing_key(),
        algorithms=["HS256"],
        audience=sessions.AUDIENCE,
        issuer=sessions.ISSUER,
    )
    assert claims["exp"] - claims["iat"] == 900
    headers = {"Authorization": f"Bearer {first.access_token}"}
    assert (await client.get("/v1/me", headers=headers)).json()["locale"] == "ru"
    row = await (
        await conn.execute("SELECT refresh_token_hash, expires_at - now() AS ttl FROM sessions")
    ).fetchone()
    assert row == {
        "refresh_token_hash": sessions.digest(first.refresh_token),
        "ttl": timedelta(days=60),
    }
    original = {"refresh_token": first.refresh_token}
    response = await client.post("/v1/auth/refresh", json=original)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert (await client.post("/v1/auth/refresh", json=original)).status_code == 401
    refreshed = response.json()
    assert refreshed["refresh_token"] != first.refresh_token
    request = {"refresh_token": refreshed["refresh_token"]}
    assert (await client.post("/v1/auth/logout", json=request)).status_code == 204
    assert (await client.get("/v1/me", headers=headers)).status_code == 401
    assert (await client.post("/v1/auth/refresh", json=request)).status_code == 401


async def test_expiry_and_identity_reuse(client, conn):
    first = await sessions.sign_in(conn, "email", "same@example.org", "ru")
    second = await sessions.sign_in(conn, "email", "same@example.org", "en")
    assert first.refresh_token != second.refresh_token
    assert (await (await conn.execute("SELECT count(*) AS n FROM users")).fetchone())["n"] == 1
    claims = jwt.decode(first.access_token, options={"verify_signature": False})
    claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=5)
    expired = jwt.encode(claims, sessions.signing_key(), algorithm="HS256")
    assert (
        await client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"})
    ).status_code == 401
    await conn.execute("UPDATE sessions SET expires_at = now()")
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    ).status_code == 401
    assert (
        await client.get("/v1/me", headers={"Authorization": f"Bearer {second.access_token}"})
    ).status_code == 401


async def test_concurrent_identity_creation_and_refresh(committed_auth_db_url):
    test_db_url = committed_auth_db_url
    subject = f"{uuid4()}@example.org"

    async def login():
        async with await psycopg.AsyncConnection.connect(test_db_url, row_factory=dict_row) as conn:
            return await sessions.sign_in(conn, "email", subject, "ru")

    first, second = await asyncio.gather(login(), login())
    subjects = [
        jwt.decode(t.access_token, options={"verify_signature": False})["sub"]
        for t in (first, second)
    ]
    assert subjects[0] == subjects[1]

    async def rotate_once():
        async with await psycopg.AsyncConnection.connect(test_db_url, row_factory=dict_row) as conn:
            return await sessions.rotate(conn, first.refresh_token)

    results = await asyncio.gather(rotate_once(), rotate_once(), return_exceptions=True)
    assert sum(isinstance(result, sessions.Tokens) for result in results) == 1
    denied = [result for result in results if isinstance(result, AppError)]
    assert len(denied) == 1 and denied[0].status_code == 401
    async with await psycopg.AsyncConnection.connect(test_db_url) as conn:
        await conn.execute("DELETE FROM users WHERE id = %s", (subjects[0],))


async def _age_retired(conn, seconds):
    await conn.execute(
        "UPDATE session_retired_tokens SET retired_at = retired_at - make_interval(secs => %s)",
        (seconds,),
    )


async def test_reuse_of_rotated_token_after_grace_revokes_whole_session(client, conn):
    first = await sessions.sign_in(conn, "email", "thief@example.org", "ru")
    other = await sessions.sign_in(conn, "email", "thief@example.org", "ru")  # another family
    second = (
        await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    ).json()
    third = (
        await client.post("/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    ).json()
    await _age_retired(conn, sessions.REUSE_GRACE_SECONDS + 1)
    # the first token is stale: an attacker (or a replay) presents it
    response = await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    assert response.status_code == 401
    # the revocation was committed, not rolled back with the error: the newest token is dead too
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": third["refresh_token"]})
    ).status_code == 401
    assert (
        await client.get("/v1/me", headers={"Authorization": f"Bearer {third['access_token']}"})
    ).status_code == 401
    # a different sign-in of the same user is a different family and stays alive
    assert (
        await client.get("/v1/me", headers={"Authorization": f"Bearer {other.access_token}"})
    ).status_code == 200
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": other.refresh_token})
    ).status_code == 200


async def test_reuse_within_grace_is_a_race_and_keeps_the_session(client, conn):
    first = await sessions.sign_in(conn, "email", "racer@example.org", "ru")
    winner = (
        await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    ).json()
    loser = await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    assert loser.status_code == 401
    ok = await client.post("/v1/auth/refresh", json={"refresh_token": winner["refresh_token"]})
    assert ok.status_code == 200  # the winner's chain survives


async def test_unknown_token_and_revoked_session_do_not_trigger_reuse(client, conn):
    first = await sessions.sign_in(conn, "email", "plain@example.org", "ru")
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": "never-issued"})
    ).status_code == 401
    second = (
        await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    ).json()
    await client.post("/v1/auth/logout", json={"refresh_token": second["refresh_token"]})
    await _age_retired(conn, 60)
    row = await (await conn.execute("SELECT revoked_at FROM sessions")).fetchone()
    stamp = row["revoked_at"]
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": first.refresh_token})
    ).status_code == 401
    row = await (await conn.execute("SELECT revoked_at FROM sessions")).fetchone()
    assert row["revoked_at"] == stamp  # not revoked a second time


async def test_retired_tokens_are_pruned_and_cascade(client, conn):
    first = await sessions.sign_in(conn, "email", "prune@example.org", "ru")
    refresh = first.refresh_token
    for _ in range(3):
        refresh = (await client.post("/v1/auth/refresh", json={"refresh_token": refresh})).json()[
            "refresh_token"
        ]
    count = "SELECT count(*) AS n FROM session_retired_tokens"
    assert (await (await conn.execute(count)).fetchone())["n"] == 3
    await _age_retired(conn, 61 * 86400)
    await client.post("/v1/auth/refresh", json={"refresh_token": refresh})
    assert (await (await conn.execute(count)).fetchone())["n"] == 1  # only the fresh one
    await conn.execute("DELETE FROM users")
    assert (await (await conn.execute(count)).fetchone())["n"] == 0
