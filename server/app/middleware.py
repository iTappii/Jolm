import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app import metrics
from app.logging_setup import request_id_var

log = logging.getLogger("app.request")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns X-Request-ID (honours an incoming one), exposes it to logs, logs each request."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        rid = rid[:64]
        token = request_id_var.set(rid)
        request.state.request_id = rid
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception(
                "request failed", extra={"method": request.method, "path": request.url.path}
            )
            raise
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        metrics.observe_request(
            request.method,
            getattr(route, "path", None) or "unmatched",
            response.status_code,
            elapsed,
        )
        log.info(
            "request",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 1),
            },
        )
        return response
