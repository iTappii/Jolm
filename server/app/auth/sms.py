"""Normalize phone destinations and select the SMS delivery provider."""

import logging
import re
from typing import Protocol

from app.config import get_settings
from app.errors import AppError

log = logging.getLogger(__name__)
_PHONE_INPUT = re.compile(r"\+?(?:[0-9][0-9 .-]*)?(?:\([0-9]+\)[0-9 .-]*)?")
_SEPARATORS = str.maketrans("", "", " .-()")
_E164 = re.compile(r"\+[1-9][0-9]{1,14}")
_KZ_LOCAL = re.compile(r"(?:[78])?([67][0-9]{9})")


def normalize_phone(value: str) -> str:
    value = value.strip()
    if not _PHONE_INPUT.fullmatch(value):
        raise AppError(422, "validation_error")
    number = value.translate(_SEPARATORS)
    if not number.startswith("+"):
        local = _KZ_LOCAL.fullmatch(number)
        if local is None:
            raise AppError(422, "validation_error")
        number = "+7" + local[1]
    if not _E164.fullmatch(number) or (number.startswith("+7") and len(number) != 12):
        raise AppError(422, "validation_error")
    return number


class SmsProvider(Protocol):
    async def send(self, destination: str, code: str) -> None: ...


class _StubSmsProvider:
    async def send(self, destination: str, code: str) -> None:
        log.info("SMS OTP (stub): %s", code)


def get_sms_provider() -> SmsProvider:
    settings = get_settings()
    # OPEN(SSOT §16.12): add a real provider once selected.
    if settings.app_env in {"dev", "test"} and settings.sms_provider == "stub":
        return _StubSmsProvider()
    raise AppError(503, "otp_delivery_unavailable")
