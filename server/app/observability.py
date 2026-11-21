"""Optional error reporting (Ш-51): Sentry-compatible, OFF unless SENTRY_DSN is set.

No mandatory dependency: `sentry-sdk` is an optional extra (`pip install -e "server[sentry]"`).
With a DSN but no SDK installed the process logs one warning and goes on. Request bodies and
headers are not sent (`send_default_pii=False`, and the request body is not attached);
`capture_exception` is also called by the unhandled-error handler and by the worker for jobs that
fail for good, so both appear with the request id / job id.
"""

import logging
from typing import Optional

from app.config import Settings

log = logging.getLogger(__name__)
_enabled = False


def init_error_reporting(settings: Settings) -> bool:
    global _enabled
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN is set but sentry-sdk is not installed; error reporting is off")
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=_release(),
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        max_request_body_size="never",
    )
    _enabled = True
    log.info("error reporting enabled")
    return True


def _release() -> str:
    from app import __version__

    return "jol-server@%s" % __version__


def capture_exception(exc: BaseException, request_id: Optional[str] = None) -> None:
    if not _enabled:
        return
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            if request_id:
                scope.set_tag("request_id", request_id)
            sentry_sdk.capture_exception(exc)
    except Exception:  # reporting must never break the request
        log.warning("error reporting failed", exc_info=True)
