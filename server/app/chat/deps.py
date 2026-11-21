"""Request helpers shared by guest and registered chat."""

from dataclasses import dataclass
from ipaddress import IPv6Address, ip_address
from typing import Optional
from uuid import UUID

from fastapi import Request

from app.chat.ratelimit import SlidingWindowLimiter
from app.config import Settings, get_settings
from app.errors import AppError
from app.providers.llm import LLMNotConfigured, ResilientLLM, get_llm_provider

INSTALL_HEADER = "x-install-id"


@dataclass
class ChatLimiters:
    guest_install: SlidingWindowLimiter
    guest_ip: SlidingWindowLimiter
    user: SlidingWindowLimiter


def make_limiters(settings: Settings) -> ChatLimiters:
    guest_window = settings.guest_chat_window_sec
    return ChatLimiters(
        guest_install=SlidingWindowLimiter(settings.guest_chat_install_limit, guest_window),
        guest_ip=SlidingWindowLimiter(settings.guest_chat_ip_limit, guest_window),
        user=SlidingWindowLimiter(settings.chat_user_limit, settings.chat_user_window_sec),
    )


def client_ip(request: Request) -> str:
    # TODO(proxy): behind a reverse proxy this is the proxy address; trust X-Forwarded-For only
    # from a configured proxy before deploying behind one.
    try:
        address = ip_address(request.client.host) if request.client else None
    except ValueError:
        return "unknown"
    if isinstance(address, IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return str(address) if address is not None else "unknown"


def install_id(request: Request) -> Optional[str]:
    """The `X-Install-ID` header if it is a UUID, else None (then only the IP is limited)."""
    raw = request.headers.get(INSTALL_HEADER, "")
    try:
        return str(UUID(raw.strip()))
    except ValueError:
        return None


def make_llm(request: Request) -> ResilientLLM:
    """A fresh `ResilientLLM` per request, so its token counter belongs to this request only.

    Tests inject a scripted provider as `app.state.llm_provider`.
    """
    settings = get_settings()
    provider = getattr(request.app.state, "llm_provider", None)
    if provider is None:
        try:
            provider = get_llm_provider(settings)
        except LLMNotConfigured:
            raise AppError(503, "llm_unavailable") from None
    return ResilientLLM(
        provider, timeout_sec=settings.llm_timeout_sec, max_retries=settings.llm_max_retries
    )
