"""DeepSeek adapter (Ш-53) on recorded SSE bodies through httpx.MockTransport: no network."""

import json
from typing import List

import httpx
import pytest

from app.config import Settings
from app.providers.llm import (
    Done,
    LLMError,
    LLMNotConfigured,
    LLMTimeout,
    Message,
    ResilientLLM,
    TextDelta,
    ToolCall,
    ToolSpec,
    Usage,
    collect,
    get_llm_provider,
)
from app.providers.llm.deepseek import DeepSeekLLM

HELLO = [Message(role="user", content="hi")]


def sse(*chunks) -> str:
    lines = [f"data: {json.dumps(c)}\n\n" if not isinstance(c, str) else c for c in chunks]
    return "".join(lines)


def delta(content=None, tool_calls=None, finish=None):
    d = {}
    if content is not None:
        d["content"] = content
    if tool_calls is not None:
        d["tool_calls"] = tool_calls
    return {"choices": [{"index": 0, "delta": d, "finish_reason": finish}]}


USAGE = {"choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 7}}
DONE = "data: [DONE]\n\n"


def provider(handler, **kwargs):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DeepSeekLLM("sk-test", client=client, **kwargs)


def ok(body: str, seen: List = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    return handler


async def run(p, **kwargs):
    return [e async for e in p.stream(HELLO, **kwargs)]


async def test_text_stream_with_usage_and_keepalive():
    body = sse(
        ": keep-alive\n\n",
        delta(""),
        delta("Hel"),
        delta("lo"),
        delta(None, finish="stop"),
        USAGE,
        DONE,
    )
    events = await run(provider(ok(body)))
    assert events == [TextDelta("Hel"), TextDelta("lo"), Usage(11, 7), Done("stop")]


async def test_request_shape_and_auth():
    seen: List[httpx.Request] = []
    tool = ToolSpec(name="t", description="d", parameters={"type": "object"})
    p = provider(ok(sse(delta("x", finish="stop"), USAGE, DONE), seen), model="m1")
    await run(p, tools=[tool], system="be brief")
    req = seen[0]
    assert str(req.url) == "https://api.deepseek.com/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "m1" and body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    assert body["tools"][0]["function"]["name"] == "t"


async def test_tool_call_arguments_assembled_from_deltas():
    first = [{"index": 0, "id": "call_a", "function": {"name": "update_brief", "arguments": ""}}]
    body = sse(
        delta(tool_calls=first),
        delta(tool_calls=[{"index": 0, "function": {"arguments": '{"budget'}}]),
        delta(tool_calls=[{"index": 0, "function": {"arguments": '_kzt": 5}'}}]),
        delta(tool_calls=[{"index": 1, "id": "call_b", "function": {"name": "x"}}]),
        delta(None, finish="tool_calls"),
        USAGE,
        DONE,
    )
    events = await run(provider(ok(body)))
    assert events[0] == ToolCall("call_a", "update_brief", '{"budget_kzt": 5}')
    assert events[0].arguments() == {"budget_kzt": 5}
    assert events[1] == ToolCall("call_b", "x", "{}")
    assert events[-1] == Done("tool_calls")


async def test_length_finish_and_missing_usage():
    body = sse(delta("cut", finish="length"), DONE)
    events = await run(provider(ok(body)))
    assert events == [TextDelta("cut"), Usage(0, 0), Done("length")]


async def test_history_with_tool_calls_is_replayed():
    seen: List[httpx.Request] = []
    history = [
        Message(role="user", content="go"),
        Message(role="assistant", content="", tool_calls=[ToolCall("c1", "f", '{"a": 1}')]),
        Message(role="tool", content="done", tool_call_id="c1"),
    ]
    p = provider(ok(sse(delta("k", finish="stop"), DONE), seen))
    [e async for e in p.stream(history)]
    msgs = json.loads(seen[0].content)["messages"]
    assert msgs[1]["tool_calls"][0] == {
        "id": "c1",
        "type": "function",
        "function": {"name": "f", "arguments": '{"a": 1}'},
    }
    assert msgs[2] == {"role": "tool", "tool_call_id": "c1", "content": "done"}


@pytest.mark.parametrize(
    "status, exc_type, code, retryable",
    [
        (401, LLMNotConfigured, "llm_not_configured", False),
        (402, LLMError, "llm_quota", False),
        (400, LLMError, "llm_bad_request", False),
        (429, LLMError, "llm_rate_limited", True),
        (500, LLMError, "llm_unavailable", True),
        (503, LLMError, "llm_unavailable", True),
    ],
)
async def test_http_errors_are_mapped(status, exc_type, code, retryable):
    def handler(request):
        return httpx.Response(status, json={"error": {"message": "nope"}})

    with pytest.raises(exc_type) as info:
        await run(provider(handler))
    assert info.value.code == code and info.value.retryable is retryable


async def test_timeout_and_transport_errors():
    def slow(request):
        raise httpx.ReadTimeout("t", request=request)

    with pytest.raises(LLMTimeout):
        await run(provider(slow))

    def down(request):
        raise httpx.ConnectError("c", request=request)

    with pytest.raises(LLMError) as info:
        await run(provider(down))
    assert info.value.retryable is True


async def test_malformed_chunk_is_error():
    with pytest.raises(LLMError) as info:
        await run(provider(ok("data: {not json\n\n")))
    assert info.value.code == "llm_bad_response"


async def test_resilient_retries_a_429_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={})
        return httpx.Response(200, text=sse(delta("ok", finish="stop"), USAGE, DONE))

    async def no_sleep(_):
        return None

    llm = ResilientLLM(provider(handler), sleep=no_sleep)
    done = await collect(llm.stream(HELLO))
    assert done.text == "ok" and len(calls) == 2 and llm.counter.total == 18


async def test_resilient_turns_401_into_error_event_without_retry():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, json={})

    llm = ResilientLLM(provider(handler))
    with pytest.raises(LLMError) as info:
        await collect(llm.stream(HELLO))
    assert info.value.code == "llm_not_configured" and len(calls) == 1


# --- factory -----------------------------------------------------------------------------------


def settings(**values):
    return Settings(_env_file=None, **values)


def test_empty_key_is_clear_not_configured_error():
    with pytest.raises(LLMNotConfigured) as info:
        # explicit empty key: the owner's .env may hold a real one, the test must not depend on it
        get_llm_provider(settings(llm_provider="deepseek", deepseek_api_key=""))
    assert "DEEPSEEK_API_KEY" in str(info.value)


def test_factory_builds_deepseek_with_defaults_and_overrides():
    p = get_llm_provider(settings(llm_provider="DeepSeek", deepseek_api_key="k"))
    assert isinstance(p, DeepSeekLLM)
    assert (p.model, p.base_url) == ("deepseek-chat", "https://api.deepseek.com")
    p = get_llm_provider(
        settings(
            llm_provider="deepseek",
            deepseek_api_key="k",
            deepseek_model="deepseek-reasoner",
            deepseek_base_url="https://example.test/",
        )
    )
    assert (p.model, p.base_url) == ("deepseek-reasoner", "https://example.test")


def test_key_is_not_leaked_in_settings_repr():
    assert "sk-secret" not in repr(settings(deepseek_api_key="sk-secret"))


# --- Ш-66: output cap -------------------------------------------------------------------------


async def test_max_tokens_is_sent_and_a_length_finish_ends_cleanly():
    seen: List = []
    body = sse(delta("Cut of"), delta(None, finish="length"), USAGE, DONE)
    llm = provider(ok(body, seen))
    done = await collect(llm.stream(HELLO, None, "sys", max_tokens=123))
    assert json.loads(seen[0].content)["max_tokens"] == 123
    assert done.text == "Cut of" and done.finish_reason == "length"
    assert done.usage == Usage(11, 7)


async def test_no_max_tokens_field_when_not_asked():
    seen: List = []
    llm = provider(ok(sse(delta("x", finish="stop"), USAGE, DONE), seen))
    await collect(llm.stream(HELLO))
    assert "max_tokens" not in json.loads(seen[0].content)
