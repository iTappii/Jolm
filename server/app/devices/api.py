"""Devices API (Ш-40): `POST /v1/devices` registers an install for pushes.

    POST /v1/devices  {"install_id": "<uuid>", "apns_token": "<hex>" | null, "language": "ru"|"en"}
        -> {"install_id", "user_linked": bool, "push_enabled": bool}

Bearer token optional: with a valid one the device row belongs to that user (pushes of their
trips go there); without one it is a guest device and the row is NOT linked to anyone (a device
that signed out must not keep receiving the previous user's pushes). The app calls it at launch,
after sign-in and after sign-out, and whenever APNs hands out a new token. A token that moves to
another install is taken away from the old row (one token, one device). A 401 for a bad token.
"""

import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator

from app.auth import sessions
from app.auth.api import bearer_token
from app.db import execute, fetch_one

router = APIRouter(prefix="/v1", tags=["devices"])

_TOKEN = re.compile(r"^[0-9a-fA-F]{32,200}$")


class DeviceIn(BaseModel):
    install_id: UUID
    apns_token: Optional[str] = Field(None, max_length=200)
    language: str = Field("en", pattern="^(ru|en)$")

    @field_validator("apns_token")
    @classmethod
    def _hex(cls, value: Optional[str]) -> Optional[str]:
        if value in (None, ""):
            return None
        if not _TOKEN.match(value):
            raise ValueError("apns_token must be a hex string")
        return value.lower()


@router.post("/devices")
async def register_device(payload: DeviceIn, request: Request):
    has_auth = bool(request.headers.get("authorization"))
    access = bearer_token(request) if has_auth else None
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access) if access else None
        user_id = user["id"] if user else None
        if payload.apns_token:
            await execute(
                conn,
                "UPDATE devices SET apns_token = NULL WHERE apns_token = %s AND install_id <> %s",
                (payload.apns_token, payload.install_id),
            )
        row = await fetch_one(
            conn,
            """
            INSERT INTO devices (install_id, user_id, apns_token, locale)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (install_id) DO UPDATE
                SET user_id = EXCLUDED.user_id, apns_token = EXCLUDED.apns_token,
                    locale = EXCLUDED.locale
            RETURNING install_id, user_id, apns_token
            """,
            (payload.install_id, user_id, payload.apns_token, payload.language),
        )
    return {
        "install_id": str(row["install_id"]),
        "user_linked": row["user_id"] is not None,
        "push_enabled": row["user_id"] is not None and row["apns_token"] is not None,
    }
