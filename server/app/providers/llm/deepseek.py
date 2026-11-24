"""DeepSeek adapter (Ш-53): OpenAI-compatible Chat Completions with SSE streaming and tools.

POST {base_url}/chat/completions with `stream: true`. The response is a server-sent-event stream
of `data: {json}` lines ended by `data: [DONE]`; text arrives as `choices[0].delta.content`, tool
calls as `delta.tool_calls[]` with incremental `function.arguments` pieces keyed by `index`, and
token usage in a final chunk (requested with `stream_options.include_usage`). Comment lines
(`: keep-alive`) are ignored.

Events are yielded per the contract of `base.py`: text as it comes, then the assembled tool calls,
then `Usage`, then `Done`. HTTP failures are mapped to the shared errors: 401/403 ->
`LLMNotConfigured`, 429/5xx/transport errors -> retryable `LLMError`, timeouts -> `LLMTimeout`.
Retries and the overall deadline live in `ResilientLLM`, not here.
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.providers.llm.base import (
    Done,
    LLMError,
    LLMEvent,
    LLMNotConfigured,
    LLMTimeout,
    Message,
    TextDelta,
    ToolCall,
    ToolSpec,
    Usage,
)

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com"
FINISH_REASONS = {"stop": "stop", "tool_calls": "tool_calls", "length": "length"}


def build_messages(messages: List[Message], system: Optional[str]) -> List[Dict[str, Any]]:
    """Jol messages -> OpenAI-style messages. The system text goes first as its own message."""
    out: List[Dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id or "", "content": m.content})
        elif m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments_json or "{}"},
                        }
                        for c in m.tool_calls
                    ],
                }
            )
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def build_tools(tools: List[ToolSpec]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in tools
    ]


def _http_error(status: int, body: str) -> LLMError:
    detail = ""
    try:
        detail = str(json.loads(body).get("error", {}).get("message", ""))[:200]
    except (ValueError, AttributeError):
        pass
    if status in (401, 403):
        return LLMNotConfigured(
            f"DeepSeek rejected the API key (HTTP {status}); check DEEPSEEK_API_KEY"
        )
    if status == 402:
        return LLMError("llm_quota", "DeepSeek account has insufficient balance (HTTP 402)")
    if status == 429:
        return LLMError("llm_rate_limited", "DeepSeek rate limit (HTTP 429)", retryable=True)
    if status >= 500:
        return LLMError("llm_unavailable", f"DeepSeek server error (HTTP {status})", retryable=True)
    return LLMError(
        "llm_bad_request", f"DeepSeek rejected the request (HTTP {status}) {detail}".strip()
    )


class DeepSeekLLM:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_sec: float = 60.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        if not api_key:
            raise LLMNotConfigured(
                "LLM_PROVIDER=deepseek needs DEEPSEEK_API_KEY (set it in .env, never commit it)"
            )
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_sec = timeout_sec
        self._client = client

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolSpec]] = None,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[LLMEvent]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": build_messages(messages, system),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens:  # Ш-66: the reply is cut here; finish_reason "length" -> Done("length")
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = build_tools(tools)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        client = self._client or httpx.AsyncClient(timeout=self.timeout_sec)
        try:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise _http_error(response.status_code, body)
                async for event in self._events(response):
                    yield event
        except httpx.TimeoutException:
            raise LLMTimeout(self.timeout_sec) from None
        except httpx.TransportError as exc:
            raise LLMError(
                "llm_unavailable", f"DeepSeek unreachable: {type(exc).__name__}", retryable=True
            ) from None
        finally:
            if self._client is None:
                await client.aclose()

    async def _events(self, response: httpx.Response) -> AsyncIterator[LLMEvent]:
        pending: Dict[int, Dict[str, str]] = {}  # tool call index -> id/name/arguments so far
        finish = "stop"
        usage: Optional[Usage] = None
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue  # blank separators and ": keep-alive" comments
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                raise LLMError(
                    "llm_bad_response", "DeepSeek sent a malformed stream chunk"
                ) from None
            if chunk.get("error"):
                raise LLMError("llm_unavailable", "DeepSeek reported an error mid-stream", True)
            raw_usage = chunk.get("usage")
            if raw_usage:
                usage = Usage(
                    int(raw_usage.get("prompt_tokens") or 0),
                    int(raw_usage.get("completion_tokens") or 0),
                )
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                text = delta.get("content")
                if text:
                    yield TextDelta(text)
                for part in delta.get("tool_calls") or []:
                    slot = pending.setdefault(
                        int(part.get("index", 0)), {"id": "", "name": "", "arguments": ""}
                    )
                    if part.get("id"):
                        slot["id"] = part["id"]
                    fn = part.get("function") or {}
                    if fn.get("name"):
                        slot["name"] += fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
                reason = choice.get("finish_reason")
                if reason == "insufficient_system_resource":
                    raise LLMError("llm_unavailable", "DeepSeek is out of resources", True)
                if reason:
                    finish = FINISH_REASONS.get(reason, "stop")
        for index in sorted(pending):
            slot = pending[index]
            yield ToolCall(slot["id"] or f"call_{index}", slot["name"], slot["arguments"] or "{}")
        yield usage or Usage(0, 0)
        yield Done("tool_calls" if pending and finish == "stop" else finish)  # type: ignore[arg-type]
