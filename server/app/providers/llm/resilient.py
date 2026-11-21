"""Timeouts, retries with backoff and token accounting around any `LLMProvider`."""

import asyncio
import logging
import time
from typing import AsyncIterator, Awaitable, Callable, List, Optional

from app.providers.llm.base import (
    ErrorEvent,
    LLMError,
    LLMEvent,
    LLMProvider,
    LLMTimeout,
    Message,
    ToolSpec,
    Usage,
)

log = logging.getLogger(__name__)
BACKOFF_BASE_SEC = 0.5
BACKOFF_MAX_SEC = 8.0


class TokenCounter:
    """Running token totals; `calls` counts completed turns that reported usage."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def add(self, usage: Usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.calls += 1

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class ResilientLLM:
    """Wraps a provider. `stream` never raises for provider failures: it ends with `ErrorEvent`.

    - `timeout_sec` is the deadline of one attempt (start to last event).
    - A retryable failure (retryable `ErrorEvent`, retryable `LLMError`, timeout) is retried
      with exponential backoff, but only while nothing has been yielded to the caller yet:
      text already shown to the user cannot be taken back.
    - Usage from every attempt that reports it is added to `counter`.
    """

    def __init__(
        self,
        provider: LLMProvider,
        timeout_sec: float = 60.0,
        max_retries: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.provider = provider
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.sleep = sleep
        self.counter = TokenCounter()

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolSpec]] = None,
        system: Optional[str] = None,
    ) -> AsyncIterator[LLMEvent]:
        attempt = 0
        while True:
            yielded = False
            failure: Optional[ErrorEvent] = None
            deadline = time.monotonic() + self.timeout_sec
            events = self.provider.stream(messages, tools, system).__aiter__()
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    try:
                        if remaining <= 0:
                            raise asyncio.TimeoutError
                        event = await asyncio.wait_for(events.__anext__(), remaining)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        raise LLMTimeout(self.timeout_sec) from None
                    if isinstance(event, ErrorEvent):
                        failure = event
                        break
                    if isinstance(event, Usage):
                        self.counter.add(event)
                    yielded = True
                    yield event
            except LLMError as exc:
                failure = ErrorEvent(exc.code, exc.message, exc.retryable)
            finally:
                aclose = getattr(events, "aclose", None)
                if aclose is not None:
                    await aclose()
            if failure is None:
                return
            if failure.retryable and not yielded and attempt < self.max_retries:
                delay = min(BACKOFF_BASE_SEC * 2**attempt, BACKOFF_MAX_SEC)
                attempt += 1
                log.warning("llm retry %d after %s in %.1fs", attempt, failure.code, delay)
                await self.sleep(delay)
                continue
            yield failure
            return
