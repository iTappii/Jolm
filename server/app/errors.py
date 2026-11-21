"""Uniform error format: {"error": {"code": ..., "message": ...}} localized RU/EN."""

import logging
from typing import Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import observability
from app.i18n import pick_locale, translate

log = logging.getLogger("app.errors")

_STATUS_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
}


class AppError(Exception):
    """Raise from handlers. `code` must be a key of i18n.MESSAGES (or pass `message`)."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
):
    locale = pick_locale(request.headers.get("accept-language"))
    body = {"error": {"code": code, "message": message or translate(code, locale)}}
    return JSONResponse(body, status_code=status_code, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return error_response(request, exc.status_code, exc.code, exc.message, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return error_response(request, exc.status_code, code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return error_response(request, 422, "validation_error")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"path": request.url.path})
        observability.capture_exception(exc, getattr(request.state, "request_id", None))
        return error_response(request, 500, "internal_error")
