from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.auth import sessions
from app.errors import AppError

router = APIRouter(prefix="/v1", tags=["auth"])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=256)


@router.post("/auth/refresh")
async def refresh(payload: RefreshRequest, request: Request, response: Response) -> sessions.Tokens:
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        return await sessions.rotate(conn, payload.refresh_token)


@router.post("/auth/logout", status_code=204)
async def logout(payload: RefreshRequest, request: Request):
    async with request.app.state.db.transaction() as conn:
        await sessions.revoke(conn, payload.refresh_token)
    return Response(status_code=204)


@router.get("/me")
async def me(request: Request, response: Response):
    scheme, _, access = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not access or len(access) > 8192:
        raise AppError(401, "unauthorized")
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        return await sessions.current_user(conn, access)
