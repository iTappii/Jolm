"""LLM provider contract: messages, tools, typed stream events, errors, helpers.

A provider streams typed events for one model turn:
`TextDelta`* and `ToolCall`* in provider order, then one `Usage`, then one `Done`
(or an `ErrorEvent` that ends the stream instead). Tool arguments arrive as the JSON string the
model produced (`ToolCall.arguments_json`); `parse_tool_args` validates it against a pydantic
model, which is how structured output is enforced (a tool whose schema is the wanted result).
"""

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, Protocol, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)


class Message(BaseModel):
    """One conversation message. Tool results use role "tool" with `tool_call_id`."""

    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_call_id: Optional[str] = None
    # assistant turns that called tools, so the history can be replayed to the model
    tool_calls: List["ToolCall"] = []


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema of the arguments object

    @classmethod
    def from_model(cls, name: str, description: str, model: Type[BaseModel]) -> "ToolSpec":
        return cls(name=name, description=description, parameters=model.model_json_schema())


# --- events ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str

    def arguments(self) -> Dict[str, Any]:
        """Parsed arguments object; raises `ToolArgsError` if not a JSON object."""
        try:
            value = json.loads(self.arguments_json or "{}")
        except ValueError:
            raise ToolArgsError(self.name, "arguments are not valid JSON") from None
        if not isinstance(value, dict):
            raise ToolArgsError(self.name, "arguments are not a JSON object")
        return value


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Done:
    finish_reason: Literal["stop", "tool_calls", "length"] = "stop"


@dataclass(frozen=True)
class ErrorEvent:
    code: str
    message: str
    retryable: bool = False


LLMEvent = Union[TextDelta, ToolCall, Usage, Done, ErrorEvent]
Message.model_rebuild()


# --- errors ---------------------------------------------------------------------------------


class LLMError(Exception):
    def __init__(self, code: str, message: str = "", retryable: bool = False) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.retryable = retryable


class LLMTimeout(LLMError):
    def __init__(self, seconds: float) -> None:
        super().__init__("llm_timeout", f"LLM did not finish within {seconds:g}s", retryable=True)


class LLMNotConfigured(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("llm_not_configured", message)


class ToolArgsError(ValueError):
    """The model called a tool with arguments that are not valid for it."""

    def __init__(self, tool: str, detail: str) -> None:
        super().__init__(f"tool {tool!r}: {detail}")
        self.tool = tool
        self.detail = detail


# --- contract and helpers -------------------------------------------------------------------


class LLMProvider(Protocol):
    def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolSpec]] = None,
        system: Optional[str] = None,
    ) -> AsyncIterator[LLMEvent]: ...


def parse_tool_args(call: ToolCall, model: Type[M]) -> M:
    """Validate a tool call's arguments against `model`; the only way chat code reads them."""
    try:
        return model.model_validate(call.arguments())
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, e["loc"])) or "<root>" for e in exc.errors())
        raise ToolArgsError(call.name, f"invalid arguments: {fields}") from None


@dataclass
class Completion:
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Usage = Usage(0, 0)
    finish_reason: str = "stop"


async def collect(events: AsyncIterator[LLMEvent]) -> Completion:
    """Drain a stream into a `Completion`; an `ErrorEvent` raises `LLMError`."""
    done = Completion()
    parts: List[str] = []
    async for event in events:
        if isinstance(event, TextDelta):
            parts.append(event.text)
        elif isinstance(event, ToolCall):
            done.tool_calls.append(event)
        elif isinstance(event, Usage):
            done.usage = event
        elif isinstance(event, Done):
            done.finish_reason = event.finish_reason
        elif isinstance(event, ErrorEvent):
            raise LLMError(event.code, event.message, event.retryable)
    done.text = "".join(parts)
    return done
