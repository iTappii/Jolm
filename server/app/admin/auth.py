"""Admin authentication: argon2id passwords, opaque session tokens, CSRF, login rate limit.

Choices (see TECH_PLAN Ш-10):
- Passwords: argon2id via argon2-cffi (OWASP / RFC 9106 recommended, memory-hard, salt + params
  embedded in the encoded hash so they can be raised later). hashlib.scrypt was the stdlib
  alternative, but it depends on how the interpreter's OpenSSL was built and has no
  encoded-hash/rehash tooling.
- Session: 256-bit random token in an HttpOnly cookie; only sha256(token) is stored in the DB.
- CSRF: per-session token = HMAC-SHA256(key=session token, msg=constant). Nothing extra is stored;
  an attacker without the cookie cannot compute it. The login form (no session yet) uses a
  double-submit cookie instead.
- Rate limit: failed attempts are stored in admin_login_attempts and counted per (email, ip)
  and per ip (works across several server processes).
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.db import execute, fetch_one

from . import sql

COOKIE_NAME = "jol_admin"
LOGIN_CSRF_COOKIE = "jol_admin_login_csrf"
SESSION_HOURS = 12
MIN_PASSWORD_LEN = 10
MAX_PASSWORD_LEN = 256

_hasher = PasswordHasher()
# Verified against when the e-mail is unknown, so timing does not reveal which e-mails exist.
_DUMMY_HASH = _hasher.hash("jol-dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return _hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def password_error(password: str) -> Optional[str]:
    if len(password) < MIN_PASSWORD_LEN:
        return f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов"
    if len(password) > MAX_PASSWORD_LEN:
        return "Пароль слишком длинный"
    return None


def normalize_email(email: str) -> str:
    return email.strip().lower()[:320]


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_for_session(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"jol-admin-csrf-v1", hashlib.sha256).hexdigest()


def tokens_equal(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@dataclass
class AdminSession:
    admin_id: str
    email: str
    token: str

    @property
    def csrf(self) -> str:
        return csrf_for_session(self.token)


async def load_session(conn, token: Optional[str]) -> Optional[AdminSession]:
    if not token or len(token) > 200:
        return None
    row = await fetch_one(conn, sql.SESSION_LOOKUP, (hash_token(token),))
    if row is None:
        return None
    return AdminSession(admin_id=str(row["admin_id"]), email=row["email"], token=token)


@dataclass
class LoginResult:
    ok: bool
    token: Optional[str] = None
    rate_limited: bool = False


async def login(
    conn, email: str, password: str, ip: str, max_failures: int, window_min: int
) -> LoginResult:
    """Check credentials. Never raises on bad input so the caller can commit the failure row."""
    email = normalize_email(email)
    pair = await fetch_one(conn, sql.LOGIN_FAILURES_PAIR, (email, ip, window_min))
    by_ip = await fetch_one(conn, sql.LOGIN_FAILURES_IP, (ip, window_min))
    # TODO: behind a reverse proxy `ip` must come from a trusted X-Forwarded-For.
    if pair["n"] >= max_failures or by_ip["n"] >= max_failures * 4:
        return LoginResult(ok=False, rate_limited=True)

    admin = await fetch_one(conn, sql.ADMIN_BY_EMAIL, (email,))
    good = verify_password(admin["password_hash"] if admin else _DUMMY_HASH, password)
    if not (admin and good and admin["disabled_at"] is None):
        await execute(conn, sql.LOGIN_FAILURE_INSERT, (email, ip))
        await execute(conn, sql.LOGIN_ATTEMPTS_CLEANUP)
        return LoginResult(ok=False)

    await execute(conn, sql.LOGIN_FAILURES_CLEAR, (email, ip))
    await execute(conn, sql.SESSIONS_CLEANUP)
    token = new_token()
    await execute(conn, sql.SESSION_INSERT, (admin["id"], hash_token(token), SESSION_HOURS))
    return LoginResult(ok=True, token=token)


async def logout(conn, token: Optional[str]) -> None:
    if token:
        await execute(conn, sql.SESSION_REVOKE, (hash_token(token),))
