from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.auth import accounts, sessions
from app.db import fetch_all
from app.errors import AppError

router = APIRouter(prefix="/v1", tags=["auth"])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)


@router.post("/auth/refresh")
async def refresh(payload: RefreshRequest, request: Request, response: Response) -> sessions.Tokens:
    response.headers["Cache-Control"] = "no-store"
    reused = False
    async with request.app.state.db.transaction() as conn:
        try:
            return await sessions.rotate(conn, payload.refresh_token)
        except sessions.RefreshReuse:
            reused = True  # swallow so the transaction COMMITS the revocation
    if reused:
        raise AppError(401, "unauthorized")


@router.post("/auth/logout", status_code=204)
async def logout(payload: RefreshRequest, request: Request):
    async with request.app.state.db.transaction() as conn:
        await sessions.revoke(conn, payload.refresh_token)
    return Response(status_code=204)


def bearer_token(request: Request) -> str:
    scheme, _, access = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not access or len(access) > 8192:
        raise AppError(401, "unauthorized")
    return access


@router.get("/me")
async def me(request: Request, response: Response):
    access = bearer_token(request)
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = dict(await sessions.current_user(conn, access))
        # Account identity for the profile menu (SSOT §11.4). Apple subjects are opaque ids and
        # Apple e-mail is never stored, so only email/phone identities are shown.
        rows = await fetch_all(
            conn,
            """
            SELECT provider, subject FROM auth_identities
            WHERE user_id = %s AND provider IN ('email', 'phone')
            ORDER BY created_at, provider
            """,
            (user["id"],),
        )
    for provider in ("email", "phone"):
        user[provider] = next((r["subject"] for r in rows if r["provider"] == provider), None)
    return user


@router.delete("/me", status_code=204)
async def delete_me(request: Request) -> Response:
    access = bearer_token(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        await accounts.delete_account(conn, user["id"])
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
