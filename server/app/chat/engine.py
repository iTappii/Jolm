"""Model turn with a tool loop, turned into SSE events.

`run_turn` streams the model, executes the tool calls it makes through a handler, feeds the
results back as tool messages and continues, up to `max_rounds` tool rounds. After that the
model is called once more without tools to force a plain answer.

The stream it yields never contains `done`; the caller sends `done` (or `error`) because only
the caller knows what was stored. A failed turn ends with one `error` event and
`record.error` set.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Tuple

from app import metrics
from app.i18n import MESSAGES, translate
from app.providers.llm import (
    Done,
    Message,
    TextDelta,
    ToolArgsError,
    ToolCall,
    ToolSpec,
    Usage,
)
from app.providers.llm.base import ErrorEvent

# Rounds right after these tools explain a plan: they get the larger output cap (Ш-66).
PLAN_TOOLS = frozenset({"build_trip", "remove_trip_item", "replace_trip_item"})

log = logging.getLogger(__name__)

MAX_CALLS_PER_ROUND = 6
SseEvent = Tuple[str, Dict[str, Any]]


@dataclass
class ToolOutcome:
    result: Dict[str, Any]  # JSON sent back to the model
    events: List[SseEvent] = field(default_factory=list)  # SSE events for the client
    ok: bool = True
    error: Optional[str] = None


ToolHandler = Callable[[ToolCall], Awaitable[ToolOutcome]]


@dataclass
class TurnRecord:
    """What happened in a turn; filled while the stream is consumed."""

    text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)  # audit trail
    error: Optional[Dict[str, str]] = None
    usage: Usage = Usage(0, 0)
    # Ш-64 timings, milliseconds: how long each model round took, each tool call by name, and
    # when the first text arrived (from the start of the turn). Never any user text.
    llm_rounds_ms: List[int] = field(default_factory=list)
    tools_ms: List[Dict[str, Any]] = field(default_factory=list)
    first_text_ms: Optional[int] = None
    truncated: bool = False  # Ш-66: a model reply was cut by the output cap


def error_payload(code: str, locale: str) -> Dict[str, str]:
    code = code if code in MESSAGES else "llm_error"
    return {"code": code, "message": translate(code, locale)}


async def run_turn(
    llm: Any,  # ResilientLLM (per request, so its token counter belongs to this request)
    messages: List[Message],
    tools: List[ToolSpec],
    system: str,
    handle_tool: ToolHandler,
    record: TurnRecord,
    locale: str,
    max_rounds: int,
) -> AsyncIterator[SseEvent]:
    conversation = list(messages)
    long_reply = False
    turn_started = time.perf_counter()

    def since(t0: float) -> int:
        return round((time.perf_counter() - t0) * 1000)

    try:
        for round_index in range(max_rounds + 1):
            last_round = round_index == max_rounds
            calls: List[ToolCall] = []
            round_text: List[str] = []
            round_started = time.perf_counter()
            kwargs = {"long_reply": True} if long_reply else {}
            async for event in llm.stream(
                conversation, None if last_round else tools, system, **kwargs
            ):
                if isinstance(event, TextDelta):
                    if record.first_text_ms is None:
                        record.first_text_ms = since(turn_started)
                    if not round_text and record.text and not record.text[-1].isspace():
                        record.text += "\n\n"
                        yield "text_delta", {"text": "\n\n"}
                    round_text.append(event.text)
                    record.text += event.text
                    yield "text_delta", {"text": event.text}
                elif isinstance(event, ToolCall):
                    calls.append(event)
                elif isinstance(event, ErrorEvent):
                    record.error = error_payload(event.code, locale)
                    yield "error", record.error
                    return
                elif isinstance(event, Done):
                    if event.finish_reason == "length":
                        # The cap cut the reply: what was streamed stays, the turn ends cleanly.
                        record.truncated = True
                        metrics.count_llm_truncated()
                        log.warning("model reply cut by the output token cap")
                elif isinstance(event, Usage):
                    pass
            record.llm_rounds_ms.append(since(round_started))
            if not calls or last_round:
                if calls:
                    log.warning("model kept calling tools after the tool rounds were used up")
                return
            long_reply = any(call.name in PLAN_TOOLS for call in calls)
            conversation.append(
                Message(role="assistant", content="".join(round_text), tool_calls=calls)
            )
            for index, call in enumerate(calls):
                if index >= MAX_CALLS_PER_ROUND:
                    outcome = ToolOutcome({"error": "too many tool calls at once"}, ok=False)
                else:
                    tool_started = time.perf_counter()
                    outcome = await handle_tool(call)
                    record.tools_ms.append({"name": call.name, "ms": since(tool_started)})
                audit: Dict[str, Any] = {"name": call.name, "ok": outcome.ok}
                try:
                    audit["arguments"] = call.arguments()
                except ToolArgsError:
                    audit["arguments"] = None
                if outcome.error:
                    audit["error"] = outcome.error
                record.tool_calls.append(audit)
                for name, data in outcome.events:
                    yield name, data
                conversation.append(
                    Message(
                        role="tool",
                        content=json.dumps(outcome.result, ensure_ascii=False, default=str),
                        tool_call_id=call.id,
                    )
                )
    except Exception:
        # Raised by a tool handler (database failure, bug); provider failures never raise here.
        log.exception("chat turn failed")
        record.error = error_payload("internal_error", locale)
        yield "error", record.error
    finally:
        counter = getattr(llm, "counter", None)
        if counter is not None:
            record.usage = Usage(counter.input_tokens, counter.output_tokens)
