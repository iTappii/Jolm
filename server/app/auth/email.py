"""Delivery adapters and input validation for email OTP codes."""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Literal, Protocol

from email_validator import EmailNotValidError, validate_email
from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import ROOT, get_settings
from app.errors import AppError

log = logging.getLogger(__name__)


class EmailProvider(Protocol):
    async def send(self, destination: str, code: str) -> None: ...


def normalize_email(value: str) -> str:
    try:
        address = validate_email(value.strip(), check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        raise AppError(422, "otp_invalid_destination") from None
    return address.ascii_email.lower()


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    smtp_host: str = Field(min_length=1)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_tls: Literal["starttls", "implicit"] = "starttls"
    smtp_from: str
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")


class DevEmailProvider:
    async def send(self, destination: str, code: str) -> None:
        log.info("Development email OTP: %s", code)


class SmtpEmailProvider:
    def __init__(self, settings: EmailSettings, sender: str) -> None:
        self.settings = settings
        self.sender = sender

    async def send(self, destination: str, code: str) -> None:
        try:
            await asyncio.to_thread(self._send, destination, code)
        except (OSError, smtplib.SMTPException):
            log.warning("Email OTP delivery failed")
            raise AppError(503, "otp_delivery_unavailable") from None

    def _send(self, destination: str, code: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = destination
        message["Subject"] = "Jol sign-in code"
        message.set_content(f"Your Jol sign-in code is {code}. It expires in 10 minutes.")
        settings = self.settings
        context = ssl.create_default_context()
        if settings.smtp_tls == "implicit":
            client = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=10, context=context
            )
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        with client:
            if settings.smtp_tls == "starttls":
                client.starttls(context=context)
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            client.send_message(message)


def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.email_provider == "stub" and settings.app_env in {"dev", "test"}:
        return DevEmailProvider()
    if settings.email_provider == "smtp":
        try:
            smtp = EmailSettings()
            sender = normalize_email(smtp.smtp_from)
        except (AppError, ValidationError):
            raise AppError(503, "otp_delivery_unavailable") from None
        if bool(smtp.smtp_username) == bool(smtp.smtp_password.get_secret_value()):
            return SmtpEmailProvider(smtp, sender)
    raise AppError(503, "otp_delivery_unavailable")
