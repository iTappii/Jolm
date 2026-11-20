import logging

from fastapi import APIRouter, Request

from app import __version__
from app.config import get_settings
from app.db import fetch_one
from app.errors import AppError
from app.system import sql

router = APIRouter()
log = logging.getLogger("app.system")


@router.get("/health")
async def health(request: Request):
    try:
        async with request.app.state.db.transaction() as conn:
            row = await fetch_one(conn, sql.HEALTH)
        if not row or row["ok"] != 1:
            raise RuntimeError("unexpected health result")
    except Exception:
        log.exception("health check failed")
        raise AppError(503, "db_unavailable") from None
    return {"status": "ok", "version": __version__}


@router.get("/v1/meta")
async def meta():
    settings = get_settings()
    return {"version": __version__, "min_ios_version": settings.min_ios_version}
