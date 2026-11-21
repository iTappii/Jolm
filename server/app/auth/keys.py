"""Separate secrets for separate jobs (Ш-51; reviews Ш-25 №1, Ш-28-server №1).

Before: one `AUTH_SECRET` signed access tokens, keyed the OTP / IP HMACs, signed the Apple
nonce and (derived) encrypted the stored Apple refresh tokens, so leaking or rotating it hit
everything at once. Now each purpose has its own setting:

| purpose                      | setting                  | form                         |
|------------------------------|--------------------------|------------------------------|
| access-token signature (JWT) | `JWT_SECRET`             | >= 32 bytes                  |
| OTP / destination / IP HMAC  | `OTP_SECRET`             | >= 32 bytes                  |
| Sign in with Apple nonce     | `APPLE_CHALLENGE_SECRET` | >= 32 bytes                  |
| tokens stored at rest        | `TOKEN_ENCRYPTION_KEYS`  | Fernet keys, first encrypts  |

`dev` / `test` (APP_ENV): a missing one falls back to `AUTH_SECRET` (the old behaviour, so existing
dev databases keep working). Any other APP_ENV: all four must be set, each >= 32 bytes and
different from the others, else `validate()` raises and the API / worker refuse to start.

Rotating a signing secret logs everybody out (JWT) or invalidates pending codes / nonces (minutes)
- nothing else breaks. Rotating encryption keys loses nothing: put the new key FIRST in
`TOKEN_ENCRYPTION_KEYS`, keep the old after it, run `python -m app.auth.keys rotate`, then drop
the old key. Moving from the pre-Ш-51 derived key: see docs/deploy.md ("Секреты").

CLI: `python -m app.auth.keys generate | check | rotate`.
"""

import base64
import hashlib
import logging
import sys
from typing import List

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import Settings, get_settings
from app.errors import AppError

log = logging.getLogger(__name__)
MIN_BYTES = 32
DEV_ENVS = frozenset({"dev", "test"})


class SecretsError(RuntimeError):
    """The secrets are missing or malformed for this APP_ENV; startup must stop."""


def _legacy_fernet_key(auth_secret: bytes) -> bytes:
    """The key that Ш-28 derived from AUTH_SECRET (kept so old ciphertexts stay readable)."""
    return base64.urlsafe_b64encode(hashlib.sha256(b"jol:apple-refresh:" + auth_secret).digest())


def _explicit(settings: Settings, name: str) -> bytes:
    return getattr(settings, name).get_secret_value().encode()


def _signing(settings: Settings, name: str) -> bytes:
    key = _explicit(settings, name)
    if not key and settings.app_env in DEV_ENVS:
        key = _explicit(settings, "auth_secret")
    return key


def _checked(key: bytes) -> bytes:
    if len(key) < MIN_BYTES:
        raise AppError(503, "auth_unavailable")
    return key


def jwt_key() -> bytes:
    return _checked(_signing(get_settings(), "jwt_secret"))


def otp_key() -> bytes:
    return _checked(_signing(get_settings(), "otp_secret"))


def challenge_key() -> bytes:
    return _checked(_signing(get_settings(), "apple_challenge_secret"))


def _fernet_keys(settings: Settings) -> List[bytes]:
    keys = [
        k.strip().encode() for k in _explicit(settings, "token_encryption_keys").decode().split(",")
    ]
    keys = [k for k in keys if k]
    legacy = _explicit(settings, "legacy_token_secret")
    if not keys and settings.app_env in DEV_ENVS:
        auth = _explicit(settings, "auth_secret")
        if auth:
            keys = [_legacy_fernet_key(auth)]
    elif legacy:
        keys = keys + [_legacy_fernet_key(legacy)]  # decrypt-only: it is last
    return keys


def token_cipher() -> MultiFernet:
    keys = _fernet_keys(get_settings())
    if not keys:
        raise AppError(503, "auth_unavailable")
    try:
        return MultiFernet([Fernet(k) for k in keys])
    except (ValueError, TypeError):
        raise AppError(503, "auth_unavailable") from None


def encrypt(token: str) -> str:
    return token_cipher().encrypt(token.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Raises `InvalidToken` when no configured key can read it."""
    return token_cipher().decrypt(ciphertext.encode()).decode()


def rotate_ciphertext(ciphertext: str) -> str:
    return token_cipher().rotate(ciphertext.encode()).decode()


def validate(settings: Settings) -> None:
    """Refuse to start with missing / weak / shared secrets outside dev and test."""
    if settings.app_env in DEV_ENVS:
        return
    problems = []
    values = {}
    for name in ("jwt_secret", "otp_secret", "apple_challenge_secret"):
        raw = _explicit(settings, name)
        values[name] = raw
        if len(raw) < MIN_BYTES:
            problems.append("%s must be set and at least %d bytes" % (name.upper(), MIN_BYTES))
    seen = {}
    for name, raw in values.items():
        if raw and raw in seen:
            problems.append("%s must differ from %s" % (name.upper(), seen[raw].upper()))
        seen.setdefault(raw, name)
    auth = _explicit(settings, "auth_secret")
    if auth and any(auth == v for v in values.values()):
        problems.append("a purpose secret must not equal AUTH_SECRET (the legacy shared key)")
    keys = _fernet_keys(settings)
    explicit_keys = [
        k for k in _explicit(settings, "token_encryption_keys").split(b",") if k.strip()
    ]
    if not explicit_keys:
        problems.append("TOKEN_ENCRYPTION_KEYS must be set (python -m app.auth.keys generate)")
    else:
        try:
            for key in keys:
                Fernet(key)
        except (ValueError, TypeError):
            problems.append("TOKEN_ENCRYPTION_KEYS holds an invalid Fernet key")
    if problems:
        raise SecretsError("; ".join(problems))


# --- CLI ---------------------------------------------------------------------------------


def _generate() -> None:
    import secrets

    for name in ("JWT_SECRET", "OTP_SECRET", "APPLE_CHALLENGE_SECRET"):
        print("%s=%s" % (name, secrets.token_urlsafe(48)))
    print("TOKEN_ENCRYPTION_KEYS=%s" % Fernet.generate_key().decode())


async def _rotate() -> int:
    from app.db import Database, execute, fetch_all

    settings = get_settings()
    db = Database(settings.database_url, 1, 2)
    await db.open()
    changed = failed = 0
    try:
        async with db.transaction() as conn:
            rows = await fetch_all(
                conn,
                "SELECT id, provider_refresh_token FROM auth_identities"
                " WHERE provider_refresh_token IS NOT NULL FOR UPDATE",
            )
            for row in rows:
                try:
                    new = rotate_ciphertext(row["provider_refresh_token"])
                except InvalidToken:
                    failed += 1
                    continue
                if new != row["provider_refresh_token"]:
                    await execute(
                        conn,
                        "UPDATE auth_identities SET provider_refresh_token = %s WHERE id = %s",
                        (new, row["id"]),
                    )
                    changed += 1
    finally:
        await db.close()
    print("re-encrypted: %d, unreadable with the configured keys: %d" % (changed, failed))
    return 1 if failed else 0


def main(argv: List[str]) -> int:
    command = argv[0] if argv else ""
    if command == "generate":
        _generate()
        return 0
    if command == "check":
        try:
            validate(get_settings())
            token_cipher()
        except (SecretsError, AppError) as exc:
            print("secrets: %s" % exc)
            return 1
        print("secrets: ok (APP_ENV=%s)" % get_settings().app_env)
        return 0
    if command == "rotate":
        import asyncio

        return asyncio.run(_rotate())
    print("usage: python -m app.auth.keys generate | check | rotate")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
