"""Scripted LLM for tests and local development: no network, deterministic output.

Two ways to script it:

    FakeLLM([Step(text=["Hi"]), Step(tool_calls=[FakeToolCall("x", {"a": 1})])])
        each `stream()` call plays the next step (the last one repeats);
    FakeLLM(rules=[(r"budget", Step(text=["How much?"]))], default=Step(...))
        the first rule whose pattern matches the last user message (regex, case-insensitive)
        wins; no match plays `default`.

Every call is recorded in `calls` so tests can assert what the chat layer sent.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple, Union

from app.providers.llm.base import (
    Done,
    ErrorEvent,
    LLMError,
    LLMEvent,
    Message,
    TextDelta,
    ToolCall,
    ToolSpec,
    Usage,
)


@dataclass(frozen=True)
class FakeToolCall:
    name: str
    arguments: Union[Dict[str, Any], str]  # a str is sent as-is (to script malformed JSON)
    id: Optional[str] = None


@dataclass(frozen=True)
class Step:
    """One scripted model turn."""

    text: Sequence[str] = ()  # one TextDelta per item
    tool_calls: Sequence[FakeToolCall] = ()
    delay_sec: float = 0.0  # sleep before the first event (to trigger timeouts)
    # fail before streaming anything: raise LLMError, or yield ErrorEvent when `error_event`
    error: Optional[LLMError] = None
    error_event: bool = False
    # fail after the text/tool events were already streamed (cannot be retried)
    error_after: Optional[LLMError] = None
    usage: Optional[Usage] = None  # default: estimated from message and output sizes


@dataclass
class Call:
    messages: List[Message]
    tools: Optional[List[ToolSpec]]
    system: Optional[str]
    max_tokens: Optional[int] = None


def estimate_tokens(text: str) -> int:
    """About 4 characters per token, at least 1 for non-empty text."""
    return (len(text) + 3) // 4


Rule = Tuple[str, Step]


@dataclass
class FakeLLM:
    steps: Sequence[Step] = ()
    rules: Sequence[Rule] = ()
    default: Step = field(default_factory=lambda: Step(text=["This is the fake LLM."]))
    calls: List[Call] = field(default_factory=list)

    def _pick(self, messages: List[Message]) -> Step:
        if self.rules:
            last = next((m.content for m in reversed(messages) if m.role == "user"), "")
            for pattern, step in self.rules:
                if re.search(pattern, last, re.IGNORECASE):
                    return step
            return self.default
        if self.steps:
            return self.steps[min(len(self.calls) - 1, len(self.steps) - 1)]
        return self.default

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolSpec]] = None,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMEvent]:
        self.calls.append(Call(list(messages), tools, system, max_tokens))
        step = self._pick(messages)
        if step.delay_sec:
            await asyncio.sleep(step.delay_sec)
        if step.error is not None:
            if step.error_event:
                yield ErrorEvent(step.error.code, step.error.message, step.error.retryable)
                return
            raise step.error
        output = []
        left = (
            max_tokens * 4 if max_tokens else None
        )  # characters left under the cap (~4 per token)
        cut = False
        for chunk in step.text:
            if left is not None:
                if left <= 0:
                    cut = True
                    break
                if len(chunk) > left:  # like a real model: the reply stops mid-word at the cap
                    chunk, cut = chunk[:left], True
                left -= len(chunk)
            output.append(chunk)
            yield TextDelta(chunk)
            if cut:
                break
        for index, call in enumerate([] if cut else step.tool_calls):
            arguments = (
                call.arguments if isinstance(call.arguments, str) else json.dumps(call.arguments)
            )
            output.append(call.name + arguments)
            yield ToolCall(call.id or f"call_{len(self.calls)}_{index}", call.name, arguments)
        if step.error_after is not None:
            raise step.error_after
        prompt = (system or "") + "".join(m.content for m in messages)
        yield step.usage or Usage(estimate_tokens(prompt), estimate_tokens("".join(output)))
        yield Done("length" if cut else "tool_calls" if step.tool_calls else "stop")
