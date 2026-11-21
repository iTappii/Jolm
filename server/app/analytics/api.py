"""Analytics events from the app (Ш-50). Prefix /v1/analytics.

    POST /v1/analytics/events
        headers: X-Install-ID (required, UUID), Authorization: Bearer (optional)
        body:    {"sent_at": ISO-8601 with zone?,
                  "events": [{"id": uuid, "name": "app_launch", "ts": ISO-8601 with zone?,
                              "place_id": uuid?, "props": {...}}]}   1..50 events
        -> 200 {"accepted": n, "duplicates": n, "rejected": n}

- The path is not `/v1/events`: that is the city events list (Ш-48).
- Client names: app_install, app_launch, directions_start (props: mode; place_id optional).
  Other names, including the server-only ones, are `rejected`, the rest of the batch is stored.
  Unknown property keys are dropped. `id` makes a retry safe (a repeat is a `duplicate`).
- `ts`/`sent_at`: the device clock. The server uses the event's age (`sent_at - ts`), so a wrong
  device clock does not matter; events older than 7 days are rejected. Both are optional.
- A bad or expired bearer is ignored (the event is stored for the install only): analytics must
  not fail because the session is stale.
- 400 `invalid_install_id`, 413 `payload_too_large` (32 KB), 422 `validation_error`,
  429 `rate_limited` (per install and per IP, in-process like the chat limits, Ш-30).
- No coordinates and no text are accepted. "I am here" is the check-in of Ш-47, not an event here.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError

from app.analytics import service
from app.analytics.schemas import EventBatch
from app.auth import sessions
from app.chat.deps import client_ip
from app.chat.ratelimit import SlidingWindowLimiter, acquire
from app.config import Settings
from app.errors import AppError
from app.live import clock

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])

MAX_BODY_BYTES = 32 * 1024


@dataclass
class AnalyticsLimiters:
    install: SlidingWindowLimiter
    ip: SlidingWindowLimiter


def make_limiters(settings: Settings) -> AnalyticsLimiters:
    window = settings.analytics_window_sec
    return AnalyticsLimiters(
        install=SlidingWindowLimiter(settings.analytics_install_limit, window),
        ip=SlidingWindowLimiter(settings.analytics_ip_limit, window),
    )


def _install_id(request: Request) -> UUID:
    try:
        return UUID(request.headers.get("x-install-id", "").strip())
    except ValueError:
        raise AppError(400, "invalid_install_id") from None


def _bearer(request: Request) -> Optional[str]:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and 0 < len(token) <= 8192 else None


@router.post("/events")
async def post_events(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    install = _install_id(request)
    limiters = request.app.state.analytics_limiters
    wait = acquire(
        [(limiters.install, "install:%s" % install), (limiters.ip, "ip:%s" % client_ip(request))]
    )
    if wait:
        raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)})
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise AppError(413, "payload_too_large")
    try:
        batch = EventBatch.model_validate_json(raw)
    except ValidationError:
        raise AppError(422, "validation_error") from None
    async with request.app.state.db.transaction() as conn:
        user_id = None
        token = _bearer(request)
        if token:
            try:
                user_id = (await sessions.current_user(conn, token))["id"]
            except AppError:
                user_id = None
        return await service.ingest(conn, install, user_id, batch, clock.now())
