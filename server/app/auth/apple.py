"""Validate native Apple identity tokens and exchange them for Jol sessions."""

import logging
import secrets
import threading
import time
from typing import Optional

import httpx
import jwt
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.auth import apple_grants, keys, sessions
from app.config import get_settings
from app.db import execute, fetch_one
from app.errors import AppError
from app.i18n import pick_locale

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/auth/apple", tags=["auth"])
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS = f"{APPLE_ISSUER}/auth/keys"
CHALLENGE_SECONDS = 300
CHALLENGE_AUDIENCE = "jol-apple-challenge"
JWKS_TTL_SECONDS = 3600
JWKS_RETRY_SECONDS = 30


def fetch_keys() -> dict[str, jwt.PyJWK]:
    response = httpx.get(APPLE_JWKS, timeout=3.0)
    response.raise_for_status()
    keys = {}
    for key in response.json()["keys"]:
        if key["kty"] == "RSA" and key.get("use") == "sig" and key.get("alg") == "RS256":
            keys[key["kid"]] = jwt.PyJWK.from_dict(key, algorithm="RS256")
    if not keys:
        raise ValueError("No Apple RSA signing keys")
    return keys


class AppleKeyCache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.keys: dict[str, jwt.PyJWK] = {}
        self.expires_at = 0.0
        self.retry_at = 0.0
        self.unavailable = False

    def key_for(self, kid: str) -> jwt.PyJWK:
        with self.lock:
            now = time.monotonic()
            fresh = now < self.expires_at
            if fresh and kid in self.keys:
                return self.keys[kid]
            if now >= self.retry_at:
                try:
                    self.keys = fetch_keys()
                except (httpx.HTTPError, KeyError, TypeError, ValueError, jwt.PyJWTError):
                    self.unavailable = True
                else:
                    self.expires_at = time.monotonic() + JWKS_TTL_SECONDS
                    self.unavailable = False
                self.retry_at = time.monotonic() + JWKS_RETRY_SECONDS
            if self.unavailable:
                raise AppError(503, "auth_unavailable")
            if kid not in self.keys:
                raise AppError(401, "unauthorized")
            return self.keys[kid]


key_cache = AppleKeyCache()


class Challenge(BaseModel):
    nonce: str


class AppleSignIn(BaseModel):
    identity_token: str = Field(min_length=1, max_length=8192)
    # Native authorization code; exchanged for a refresh token that account deletion revokes.
    authorization_code: Optional[str] = Field(default=None, min_length=1, max_length=2048)


@router.post("/challenge")
async def challenge(response: Response) -> Challenge:
    response.headers["Cache-Control"] = "no-store"
    return Challenge(
        nonce=jwt.encode(
            {
                "aud": CHALLENGE_AUDIENCE,
                "exp": int(time.time()) + CHALLENGE_SECONDS,
                "jti": secrets.token_urlsafe(32),
            },
            keys.challenge_key(),
            algorithm="HS256",
        )
    )


def verify_identity(token: str) -> tuple[str, str, int]:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 128:
            raise jwt.InvalidTokenError
        # Reject tokens without a live Jol nonce before an unknown kid can trigger a key refresh.
        # The nonce claim is authenticated by the Apple signature below before any state changes.
        unverified = jwt.decode(token, options={"verify_signature": False})
        nonce = unverified.get("nonce")
        if not isinstance(nonce, str) or not 1 <= len(nonce) <= 512:
            raise jwt.InvalidTokenError
        challenge_claims = jwt.decode(
            nonce,
            keys.challenge_key(),
            algorithms=["HS256"],
            audience=CHALLENGE_AUDIENCE,
            options={"require": ["aud", "exp", "jti"], "strict_aud": True},
        )
        claims = jwt.decode(
            token,
            key_cache.key_for(kid).key,
            algorithms=["RS256"],
            issuer=APPLE_ISSUER,
            audience=get_settings().apple_client_id,
            options={"require": ["iss", "aud", "exp", "sub", "nonce"], "strict_aud": True},
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
            raise jwt.InvalidTokenError
        return subject, sessions.digest(nonce), challenge_claims["exp"]
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise AppError(401, "unauthorized") from None


async def _exchange_code(subject: str, code: Optional[str]) -> Optional[str]:
    """Best effort: trade the authorization code for an encrypted refresh token.

    Sign-in never fails because of this call. Without a stored token, deleting the account
    cannot revoke the Apple grant (logged then).
    """
    if code is None:
        return None
    try:
        exchanged = await apple_grants.get_apple_grants().exchange_code(code)
        if exchanged is None:
            return None
        code_subject, refresh = exchanged
        if code_subject != subject:
            log.warning("apple authorization code belongs to another subject; ignored")
            return None
        return apple_grants.encrypt_token(refresh)
    except apple_grants.AppleGrantError as exc:
        log.warning("apple code exchange failed: %s", exc)
        return None


@router.post("")
async def sign_in(payload: AppleSignIn, request: Request, response: Response) -> sessions.Tokens:
    subject, nonce_hash, expires_at = await run_in_threadpool(
        verify_identity, payload.identity_token
    )
    response.headers["Cache-Control"] = "no-store"
    stored_token = await _exchange_code(subject, payload.authorization_code)
    async with request.app.state.db.transaction() as conn:
        await execute(conn, "DELETE FROM apple_consumed_challenges WHERE expires_at <= now()")
        consumed = await fetch_one(
            conn,
            """
            INSERT INTO apple_consumed_challenges(nonce_hash, expires_at)
            SELECT %s, to_timestamp(%s) WHERE to_timestamp(%s) > now()
            ON CONFLICT (nonce_hash) DO NOTHING
            RETURNING nonce_hash
            """,
            (nonce_hash, expires_at, expires_at),
        )
        if consumed is None:
            raise AppError(401, "unauthorized")
        tokens = await sessions.sign_in(
            conn, "apple", subject, pick_locale(request.headers.get("accept-language"))
        )
        if stored_token is not None:
            await execute(
                conn,
                """
                UPDATE auth_identities SET provider_refresh_token = %s
                WHERE provider = 'apple' AND subject = %s
                """,
                (stored_token, subject),
            )
        return tokens
