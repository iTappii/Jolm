"""Account deletion: remove the user and every row that holds personal data."""

import logging
from uuid import UUID

from app import worker
from app.auth import otp, sessions
from app.db import execute, fetch_all

log = logging.getLogger(__name__)
APPLE_REVOKE_JOB = "apple.revoke"


async def delete_account(conn, user_id: UUID) -> None:
    """Hard-delete the user inside the caller's transaction.

    Cascades (FK ON DELETE) remove identities, sessions and devices; user-authored photos are
    anonymized. OTP rows are keyed by a destination hash, not by user, so they are removed here.
    Deleting the identities also lets the same email, phone or Apple ID register again.
    If an Apple refresh token is stored, an `apple.revoke` job is enqueued in the same
    transaction; the Apple call itself never blocks or fails the deletion.
    """
    identities = await fetch_all(
        conn,
        """
        SELECT provider, subject, provider_refresh_token FROM auth_identities
        WHERE user_id = %s ORDER BY provider, subject
        """,
        (user_id,),
    )
    for identity in identities:
        # Same lock as sign-in, so a concurrent sign-in cannot revive the identity mid-delete.
        await sessions.lock_identity(conn, identity["provider"], identity["subject"])
    key = sessions.signing_key()
    for identity in identities:
        if identity["provider"] in ("email", "phone"):
            await execute(
                conn,
                "DELETE FROM otp_codes WHERE channel = %s AND destination_hash = %s",
                (
                    identity["provider"],
                    otp._digest(key, f"destination:{identity['provider']}", identity["subject"]),
                ),
            )
        elif identity["provider"] == "apple":
            if identity["provider_refresh_token"]:
                await worker.enqueue(
                    conn,
                    APPLE_REVOKE_JOB,
                    {"token": identity["provider_refresh_token"]},
                    dedupe_key=f"{APPLE_REVOKE_JOB}:{user_id}",
                )
            else:
                # CREDENTIAL GAP: no stored token, so Apple cannot be told about the deletion.
                log.warning("apple token not revoked: no refresh token stored")
    await execute(conn, "DELETE FROM users WHERE id = %s", (user_id,))
