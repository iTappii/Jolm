"""Sessions shared by verified email, phone and Apple identities."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pydantic import BaseModel

from app.config import get_settings
from app.db import execute, fetch_one
from app.errors import AppError

ACCESS_SECONDS = 15 * 60
ISSUER = "jol-api"
AUDIENCE = "jol-access"


def signing_key() -> bytes:
    key = get_settings().auth_secret.get_secret_value().encode()
    if len(key) < 32:
        raise AppError(503, "auth_unavailable")
    return key


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_SECONDS


def tokens(row, refresh: str) -> Tokens:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(row["user_id"]),
        "sid": str(row["id"]),
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_SECONDS),
    }
    return Tokens(
        access_token=jwt.encode(claims, signing_key(), algorithm="HS256"), refresh_token=refresh
    )


async def sign_in(conn, provider: str, subject: str, locale: str) -> Tokens:
    # Serialize first sign-ins for this identity before creating its user.
    await execute(
        conn,
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"identity:{provider}:{subject}",),
    )
    identity = await fetch_one(
        conn,
        """
        SELECT i.user_id, u.deleted_at FROM auth_identities i JOIN users u ON u.id = i.user_id
        WHERE i.provider = %s AND i.subject = %s
    """,
        (provider, subject),
    )
    if identity is None:
        user = await fetch_one(
            conn, "INSERT INTO users(locale) VALUES (%s) RETURNING id", (locale,)
        )
        user_id = user["id"]
        await execute(
            conn,
            "INSERT INTO auth_identities(user_id, provider, subject) VALUES (%s,%s,%s)",
            (user_id, provider, subject),
        )
    elif identity["deleted_at"] is None:
        user_id = identity["user_id"]
    else:
        raise AppError(401, "unauthorized")
    refresh = secrets.token_urlsafe(32)
    row = await fetch_one(
        conn,
        """
        INSERT INTO sessions(user_id, refresh_token_hash, expires_at)
        VALUES (%s, %s, now() + interval '60 days') RETURNING id, user_id
    """,
        (user_id, digest(refresh)),
    )
    return tokens(row, refresh)


async def rotate(conn, old: str) -> Tokens:
    refresh = secrets.token_urlsafe(32)
    row = await fetch_one(
        conn,
        """
        UPDATE sessions s SET refresh_token_hash = %s, expires_at = now() + interval '60 days'
        FROM users u WHERE s.user_id = u.id AND u.deleted_at IS NULL AND s.refresh_token_hash = %s
        AND s.revoked_at IS NULL AND s.expires_at > now() RETURNING s.id, s.user_id
    """,
        (digest(refresh), digest(old)),
    )
    if row is None:
        raise AppError(401, "unauthorized")
    return tokens(row, refresh)


async def revoke(conn, refresh: str) -> None:
    await execute(
        conn,
        """
        UPDATE sessions SET revoked_at = now() WHERE refresh_token_hash = %s AND revoked_at IS NULL
    """,
        (digest(refresh),),
    )


async def current_user(conn, access: str):
    try:
        claims = jwt.decode(
            access,
            signing_key(),
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["iat", "exp", "sub", "sid"]},
        )
        sid, uid = UUID(claims["sid"]), UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise AppError(401, "unauthorized") from None
    row = await fetch_one(
        conn,
        """
        SELECT u.id, u.locale, u.display_name FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.id = %s AND u.id = %s AND u.deleted_at IS NULL AND s.revoked_at IS NULL
        AND s.expires_at > now()
    """,
        (sid, uid),
    )
    if row is None:
        raise AppError(401, "unauthorized")
    return row
