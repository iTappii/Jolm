"""Issue and verify one-time codes shared by email and SMS sign-in."""

import hmac
import secrets
from uuid import uuid4

from app.auth import sessions
from app.db import execute, fetch_one
from app.errors import AppError

DESTINATION_LIMIT = 3
IP_LIMIT = 20
MAX_ATTEMPTS = 5


def _digest(key: bytes, purpose: str, value: str) -> str:
    return hmac.digest(key, f"jol:otp:{purpose}:{value}".encode(), "sha256").hex()


async def _lock(conn, purpose: str, value: str) -> None:
    await execute(
        conn,
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"otp:{purpose}:{value}",),
    )


async def _latest(conn, channel: str, destination_hash: str):
    return await fetch_one(
        conn,
        """
        SELECT id, code_hash, attempts, consumed_at, expires_at > clock_timestamp() AS fresh
        FROM otp_codes WHERE channel = %s AND destination_hash = %s
        ORDER BY created_at DESC, id DESC LIMIT 1
        """,
        (channel, destination_hash),
    )


async def issue(db, provider, channel: str, destination: str, ip: str) -> None:
    key = sessions.signing_key()
    destination_hash = _digest(key, f"destination:{channel}", destination)
    ip_hash = _digest(key, "ip", ip)
    code_id = uuid4()
    code = f"{secrets.randbelow(1_000_000):06d}"
    async with db.transaction() as conn:
        await _lock(conn, "destination", destination_hash)
        await _lock(conn, "ip", ip_hash)
        counts = await fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM otp_codes WHERE channel = %s AND destination_hash = %s
                 AND created_at > statement_timestamp() - interval '10 minutes') AS destination,
                (SELECT count(*) FROM otp_codes WHERE ip_hash = %s
                 AND created_at > statement_timestamp() - interval '10 minutes') AS ip
            """,
            (channel, destination_hash, ip_hash),
        )
        if counts["destination"] >= DESTINATION_LIMIT or counts["ip"] >= IP_LIMIT:
            raise AppError(429, "otp_rate_limited")
        # Reserve the rate-limit slot before delivery. A new code starts inactive.
        await execute(
            conn,
            """
            INSERT INTO otp_codes
                (id, channel, destination_hash, ip_hash, code_hash, created_at,
                 expires_at, consumed_at)
            VALUES (%s, %s, %s, %s, %s, statement_timestamp(),
                    statement_timestamp() + interval '10 minutes', statement_timestamp())
            """,
            (code_id, channel, destination_hash, ip_hash, _digest(key, str(code_id), code)),
        )

    await provider.send(destination, code)

    async with db.transaction() as conn:
        await _lock(conn, "destination", destination_hash)
        row = await _latest(conn, channel, destination_hash)
        if row["id"] == code_id and row["fresh"]:
            await execute(conn, "UPDATE otp_codes SET consumed_at = NULL WHERE id = %s", (code_id,))


async def verify(db, channel: str, destination: str, code: str, locale: str) -> sessions.Tokens:
    key = sessions.signing_key()
    destination_hash = _digest(key, f"destination:{channel}", destination)
    async with db.transaction() as conn:
        await _lock(conn, "destination", destination_hash)
        row = await _latest(conn, channel, destination_hash)
        if row and row["fresh"] and row["consumed_at"] is None and row["attempts"] < MAX_ATTEMPTS:
            if hmac.compare_digest(row["code_hash"], _digest(key, str(row["id"]), code)):
                await execute(
                    conn,
                    "UPDATE otp_codes SET consumed_at = clock_timestamp() WHERE id = %s",
                    (row["id"],),
                )
                return await sessions.sign_in(conn, channel, destination, locale)
            await execute(
                conn, "UPDATE otp_codes SET attempts = attempts + 1 WHERE id = %s", (row["id"],)
            )

    # Commit failed attempts before raising the API error.
    raise AppError(401, "otp_invalid")
