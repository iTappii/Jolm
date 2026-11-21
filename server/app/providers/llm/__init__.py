"""LLM layer (Ш-29): provider contract, fake adapter, retries/timeouts, config factory."""

from typing import Optional

from app.config import Settings, get_settings
from app.providers.llm.base import (
    Completion,
    Done,
    ErrorEvent,
    LLMError,
    LLMEvent,
    LLMNotConfigured,
    LLMProvider,
    LLMTimeout,
    Message,
    TextDelta,
    ToolArgsError,
    ToolCall,
    ToolSpec,
    Usage,
    collect,
    parse_tool_args,
)
from app.providers.llm.fake import FakeLLM
from app.providers.llm.resilient import ResilientLLM, TokenCounter

__all__ = [
    "Completion",
    "Done",
    "ErrorEvent",
    "FakeLLM",
    "LLMError",
    "LLMEvent",
    "LLMNotConfigured",
    "LLMProvider",
    "LLMTimeout",
    "Message",
    "ResilientLLM",
    "TextDelta",
    "TokenCounter",
    "ToolArgsError",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "collect",
    "get_llm_provider",
    "get_resilient_llm",
    "parse_tool_args",
]

FAKE_NAMES = {"fake", "stub"}  # "stub" is the old default in existing .env files


def get_llm_provider(settings: Optional[Settings] = None) -> LLMProvider:
    """Provider chosen by LLM_PROVIDER. `fake` only in dev/test."""
    settings = settings or get_settings()
    name = settings.llm_provider.strip().lower()
    if name in FAKE_NAMES:
        if settings.app_env in {"dev", "test"}:
            return FakeLLM()
        raise LLMNotConfigured("LLM_PROVIDER=fake is only allowed in dev and test")
    # OPEN(SSOT §16.12): add the real adapter here once the LLM provider is chosen.
    raise LLMNotConfigured(
        f"LLM provider {name!r} is not available: the real provider is not chosen yet "
        "(SSOT §16.12); use LLM_PROVIDER=fake in dev/test"
    )


def get_resilient_llm(settings: Optional[Settings] = None) -> ResilientLLM:
    settings = settings or get_settings()
    return ResilientLLM(
        get_llm_provider(settings),
        timeout_sec=settings.llm_timeout_sec,
        max_retries=settings.llm_max_retries,
    )
