"""Sign in with Apple server-to-server calls: authorization-code exchange and token revocation.

App Store rule: when an account created with Sign in with Apple is deleted, the app must revoke
the user's Apple tokens (https://appleid.apple.com/auth/revoke).

CREDENTIAL GAP: both calls need an ES256 client secret signed with a Sign in with Apple key from
the Apple Developer account (APPLE_TEAM_ID, APPLE_KEY_ID, APPLE_PRIVATE_KEY). They are not
provisioned yet, so only the stub adapter has run; the HTTP adapter is covered by mocked-HTTP
tests only and has never talked to Apple.
"""

import logging
import time
from typing import Optional, Protocol, Tuple

import httpx
import jwt
from cryptography.fernet import InvalidToken

from app.auth import keys
from app.config import Settings, get_settings

log = logging.getLogger(__name__)
APPLE_ISSUER = "https://appleid.apple.com"
TOKEN_URL = f"{APPLE_ISSUER}/auth/token"
REVOKE_URL = f"{APPLE_ISSUER}/auth/revoke"
CLIENT_SECRET_SECONDS = 300
HTTP_TIMEOUT = 5.0


class AppleGrantError(Exception):
    """Apple was unreachable or rejected the request; the caller may retry later."""


class AppleGrants(Protocol):
    async def exchange_code(self, code: str) -> Optional[Tuple[str, str]]:
        """Return (apple user id, refresh token) for an authorization code, or None."""
        ...

    async def revoke(self, refresh_token: str) -> None: ...


def credentials_configured(settings: Settings) -> bool:
    return bool(
        settings.apple_team_id
        and settings.apple_key_id
        and settings.apple_private_key.get_secret_value()
    )


def client_secret(settings: Settings) -> str:
    pem = settings.apple_private_key.get_secret_value().replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": now,
            "exp": now + CLIENT_SECRET_SECONDS,
            "aud": APPLE_ISSUER,
            "sub": settings.apple_client_id,
        },
        pem,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


class HttpAppleGrants:
    def __init__(
        self, settings: Settings, transport: Optional[httpx.AsyncBaseTransport] = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    def _form(self, **fields: str) -> dict:
        return {
            "client_id": self.settings.apple_client_id,
            "client_secret": client_secret(self.settings),
            **fields,
        }

    async def _post(self, url: str, form: dict) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, transport=self.transport) as http:
                return await http.post(url, data=form)
        except httpx.HTTPError as exc:
            raise AppleGrantError(f"Apple request failed: {type(exc).__name__}") from None

    async def exchange_code(self, code: str) -> Optional[Tuple[str, str]]:
        response = await self._post(
            TOKEN_URL, self._form(code=code, grant_type="authorization_code")
        )
        if response.status_code != 200:
            raise AppleGrantError(f"Apple token exchange returned {response.status_code}")
        try:
            body = response.json()
            refresh = body["refresh_token"]
            subject = jwt.decode(body["id_token"], options={"verify_signature": False})["sub"]
        except (ValueError, KeyError, TypeError, jwt.PyJWTError):
            raise AppleGrantError("Apple token response is malformed") from None
        if not isinstance(refresh, str) or not isinstance(subject, str):
            raise AppleGrantError("Apple token response is malformed")
        return subject, refresh

    async def revoke(self, refresh_token: str) -> None:
        response = await self._post(
            REVOKE_URL, self._form(token=refresh_token, token_type_hint="refresh_token")
        )
        if response.status_code == 200:
            return
        if response.status_code == 400 and _error(response) == "invalid_grant":
            # Already revoked or expired: nothing left to revoke, do not retry forever.
            log.info("apple token already revoked")
            return
        raise AppleGrantError(f"Apple revoke returned {response.status_code}")


def _error(response: httpx.Response) -> Optional[str]:
    try:
        value = response.json().get("error")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


class StubAppleGrants:
    """Dev/test adapter: no network, nothing stored, revocation is only logged."""

    async def exchange_code(self, code: str) -> Optional[Tuple[str, str]]:
        return None

    async def revoke(self, refresh_token: str) -> None:
        log.warning("apple revoke skipped (stub adapter, Apple credentials not configured)")


class MissingCredentialsGrants(StubAppleGrants):
    """Outside dev/test without credentials: revocation fails loudly so the job stays visible."""

    async def revoke(self, refresh_token: str) -> None:
        raise AppleGrantError("Apple credentials are not configured (APPLE_TEAM_ID/KEY_ID/KEY)")


def get_apple_grants() -> AppleGrants:
    settings = get_settings()
    if credentials_configured(settings):
        return HttpAppleGrants(settings)
    if settings.app_env in {"dev", "test"}:
        return StubAppleGrants()
    return MissingCredentialsGrants()


# --- encryption of the stored refresh token (keys: app/auth/keys.py) ------------------------


def encrypt_token(token: str) -> str:
    return keys.encrypt(token)


def decrypt_token(ciphertext: str) -> str:
    try:
        return keys.decrypt(ciphertext)
    except InvalidToken:
        raise AppleGrantError("Stored Apple token cannot be decrypted") from None
