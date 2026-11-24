import hmac
import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app import __version__, llm_budget, metrics
from app.config import get_settings
from app.db import fetch_one
from app.errors import AppError
from app.system import sql

router = APIRouter()
log = logging.getLogger("app.system")


async def _check_db(request: Request) -> None:
    try:
        async with request.app.state.db.transaction() as conn:
            row = await fetch_one(conn, sql.HEALTH)
        if not row or row["ok"] != 1:
            raise RuntimeError("unexpected health result")
    except Exception:
        log.exception("health check failed")
        raise AppError(503, "db_unavailable") from None


@router.get("/livez")
async def livez():
    """Liveness: the process answers. No database: a DB outage must not restart the API."""
    return {"status": "ok"}


@router.get("/readyz")
@router.get("/health")
async def health(request: Request):
    """Readiness (and the original /health): the database answers. Load balancers use this."""
    await _check_db(request)
    return {"status": "ok", "version": __version__}


@router.get("/v1/meta")
async def meta():
    settings = get_settings()
    return {"version": __version__, "min_ios_version": settings.min_ios_version}


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint(request: Request):
    """Prometheus text. Needs `Authorization: Bearer $METRICS_TOKEN`; without a token it is open
    in dev/test and does not exist (404) anywhere else, so it is never exposed by accident."""
    settings = get_settings()
    token = settings.metrics_token.get_secret_value()
    if token:
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
            raise AppError(401, "unauthorized")
    elif settings.app_env not in ("dev", "test"):
        raise AppError(404, "not_found")
    gauges = []
    try:
        async with request.app.state.db.transaction() as conn:
            row = await fetch_one(conn, sql.JOB_GAUGES)
        gauges = [
            ("jol_jobs_pending", "Jobs waiting or retrying", row["pending"]),
            ("jol_jobs_overdue_seconds", "Age of the oldest job past its run time", row["overdue"]),
            (
                "jol_jobs_dead",
                "Dead jobs (kept until cleanup)",
                row["dead"],
            ),
        ]
        async with request.app.state.db.transaction() as conn:  # Ш-66
            used = await llm_budget.global_used_today(conn)
        gauges += [
            ("jol_llm_tokens_today", "Model tokens used today (all users)", used),
            (
                "jol_llm_tokens_budget",
                "Daily global model token budget (0 = no limit)",
                settings.llm_daily_tokens_global,
            ),
        ]
    except Exception:
        log.warning("metrics: job gauges unavailable", exc_info=True)
    return PlainTextResponse(
        metrics.render(gauges), media_type="text/plain; version=0.0.4; charset=utf-8"
    )
