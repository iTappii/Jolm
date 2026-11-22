import asyncio
from typing import List

import pytest
from pydantic import BaseModel, Field

from app.config import Settings
from app.providers.llm import (
    Done,
    ErrorEvent,
    FakeLLM,
    LLMError,
    LLMNotConfigured,
    LLMTimeout,
    Message,
    ResilientLLM,
    TextDelta,
    ToolArgsError,
    ToolCall,
    ToolSpec,
    Usage,
    collect,
    get_llm_provider,
    get_resilient_llm,
    parse_tool_args,
)
from app.providers.llm.fake import FakeToolCall, Step

HELLO = [Message(role="user", content="hi")]


class BriefUpdate(BaseModel):
    budget_kzt: int = Field(gt=0)
    has_lodging: bool


async def events(provider, messages=HELLO, **kwargs) -> List:
    return [event async for event in provider.stream(messages, **kwargs)]


def no_sleep():
    delays: List[float] = []

    async def sleep(seconds):
        delays.append(seconds)

    return sleep, delays


# --- streaming order -------------------------------------------------------------------------


async def test_stream_order_text_then_tool_calls_then_usage_and_done():
    llm = FakeLLM(
        [
            Step(
                text=["Hel", "lo"],
                tool_calls=[FakeToolCall("add_graph_node", {"text": "dates"}, id="c1")],
            )
        ]
    )
    got = await events(llm, system="sys")
    assert got[:2] == [TextDelta("Hel"), TextDelta("lo")]
    assert got[2] == ToolCall("c1", "add_graph_node", '{"text": "dates"}')
    assert isinstance(got[3], Usage) and got[4] == Done("tool_calls")
    assert len(got) == 5


async def test_plain_text_turn_finishes_with_stop():
    got = await events(FakeLLM([Step(text=["ok"])]))
    assert [type(e) for e in got] == [TextDelta, Usage, Done]
    assert got[-1] == Done("stop")


async def test_steps_play_in_order_and_last_repeats_and_calls_are_recorded():
    llm = FakeLLM([Step(text=["one"]), Step(text=["two"])])
    tools = [ToolSpec(name="t", description="d", parameters={"type": "object"})]
    texts = [(await collect(llm.stream(HELLO, tools, "sys"))).text for _ in range(3)]
    assert texts == ["one", "two", "two"]
    assert llm.calls[0].system == "sys" and llm.calls[0].tools == tools
    assert llm.calls[0].messages == HELLO


async def test_rules_match_last_user_message():
    llm = FakeLLM(
        rules=[("budget", Step(text=["How much?"])), ("^hi$", Step(text=["Hello"]))],
        default=Step(text=["?"]),
    )

    async def reply(text):
        history = [Message(role="user", content="hi"), Message(role="assistant", content="x")]
        return (await collect(llm.stream(history + [Message(role="user", content=text)]))).text

    assert await reply("My BUDGET is big") == "How much?"
    assert await reply("hi") == "Hello"
    assert await reply("whatever") == "?"


# --- tool calls and structured output --------------------------------------------------------


async def test_tool_call_args_validated_against_pydantic_model():
    llm = FakeLLM(
        [
            Step(
                tool_calls=[
                    FakeToolCall("update_trip_brief", {"budget_kzt": 500000, "has_lodging": True})
                ]
            )
        ]
    )
    done = await collect(llm.stream(HELLO))
    parsed = parse_tool_args(done.tool_calls[0], BriefUpdate)
    assert parsed == BriefUpdate(budget_kzt=500000, has_lodging=True)
    assert done.finish_reason == "tool_calls"


@pytest.mark.parametrize(
    "arguments",
    [
        "{not json",
        "[1, 2]",
        {"budget_kzt": 0, "has_lodging": True},
        {"budget_kzt": "lots", "has_lodging": True},
        {"has_lodging": True},
    ],
)
async def test_invalid_tool_args_raise_tool_args_error(arguments):
    call = await collect(FakeLLM([Step(tool_calls=[FakeToolCall("t", arguments)])]).stream(HELLO))
    with pytest.raises(ToolArgsError) as error:
        parse_tool_args(call.tool_calls[0], BriefUpdate)
    assert error.value.tool == "t"
    assert "lots" not in str(error.value)  # values are never echoed, only field names


def test_tool_spec_from_pydantic_model():
    spec = ToolSpec.from_model("update_trip_brief", "Record trip facts", BriefUpdate)
    assert spec.parameters["required"] == ["budget_kzt", "has_lodging"]


async def test_collect_raises_on_error_event():
    llm = FakeLLM([Step(error=LLMError("boom", "bad", retryable=False), error_event=True)])
    with pytest.raises(LLMError) as error:
        await collect(llm.stream(HELLO))
    assert (error.value.code, error.value.retryable) == ("boom", False)


# --- timeout, retry, backoff -----------------------------------------------------------------


async def test_timeout_ends_with_retryable_error_event_after_retries():
    sleep, delays = no_sleep()
    llm = ResilientLLM(
        FakeLLM([Step(text=["late"], delay_sec=5)]), timeout_sec=0.05, max_retries=2, sleep=sleep
    )
    got = await events(llm)
    assert got == [ErrorEvent("llm_timeout", str(LLMTimeout(0.05)), True)]
    assert len(llm.provider.calls) == 3 and delays == [0.5, 1.0]


async def test_timeout_then_success():
    sleep, _ = no_sleep()
    provider = FakeLLM([Step(delay_sec=5), Step(text=["fine"])])
    llm = ResilientLLM(provider, timeout_sec=0.05, max_retries=1, sleep=sleep)
    assert (await collect(llm.stream(HELLO))).text == "fine"


async def test_slow_but_within_deadline_is_not_a_timeout():
    llm = ResilientLLM(FakeLLM([Step(text=["ok"], delay_sec=0.01)]), timeout_sec=2)
    assert (await collect(llm.stream(HELLO))).text == "ok"


@pytest.mark.parametrize("as_event", [False, True], ids=["raised", "event"])
async def test_retryable_error_is_retried_with_exponential_backoff(as_event):
    sleep, delays = no_sleep()
    flaky = LLMError("rate_limited", "429", retryable=True)
    provider = FakeLLM([Step(error=flaky, error_event=as_event)] * 2 + [Step(text=["third time"])])
    llm = ResilientLLM(provider, max_retries=3, sleep=sleep)
    assert (await collect(llm.stream(HELLO))).text == "third time"
    assert len(provider.calls) == 3 and delays == [0.5, 1.0]


async def test_retries_are_bounded_and_last_error_is_reported():
    sleep, delays = no_sleep()
    provider = FakeLLM([Step(error=LLMError("overloaded", "503", retryable=True))])
    llm = ResilientLLM(provider, max_retries=2, sleep=sleep)
    assert await events(llm) == [ErrorEvent("overloaded", "503", True)]
    assert len(provider.calls) == 3 and len(delays) == 2


async def test_non_retryable_error_is_not_retried():
    sleep, delays = no_sleep()
    provider = FakeLLM([Step(error=LLMError("bad_request", "400"))])
    llm = ResilientLLM(provider, max_retries=3, sleep=sleep)
    assert await events(llm) == [ErrorEvent("bad_request", "400", False)]
    assert len(provider.calls) == 1 and delays == []


async def test_no_retry_after_output_was_already_streamed():
    sleep, delays = no_sleep()
    provider = FakeLLM(
        [Step(text=["partial"], error_after=LLMError("dropped", "reset", retryable=True))]
    )
    llm = ResilientLLM(provider, max_retries=3, sleep=sleep)
    got = await events(llm)
    assert got == [TextDelta("partial"), ErrorEvent("dropped", "reset", True)]
    assert len(provider.calls) == 1 and delays == []


async def test_cancellation_propagates():
    llm = ResilientLLM(FakeLLM([Step(text=["x"], delay_sec=5)]), timeout_sec=10)
    task = asyncio.ensure_future(collect(llm.stream(HELLO)))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# --- token accounting ------------------------------------------------------------------------


async def test_usage_is_reported_and_accumulated():
    provider = FakeLLM([Step(text=["a"], usage=Usage(10, 3)), Step(text=["b"], usage=Usage(20, 4))])
    llm = ResilientLLM(provider)
    first = await collect(llm.stream(HELLO))
    await collect(llm.stream(HELLO))
    assert first.usage == Usage(10, 3) and first.usage.total == 13
    assert (llm.counter.input_tokens, llm.counter.output_tokens) == (30, 7)
    assert (llm.counter.total, llm.counter.calls) == (37, 2)


async def test_default_usage_estimate_grows_with_prompt_and_output():
    llm = FakeLLM([Step(text=["x" * 40])])
    short = await collect(llm.stream(HELLO))
    long = await collect(llm.stream(HELLO, system="s" * 400))
    assert short.usage.output_tokens == 10 and long.usage.input_tokens > short.usage.input_tokens


async def test_failed_attempts_without_usage_are_not_counted():
    sleep, _ = no_sleep()
    provider = FakeLLM(
        [Step(error=LLMError("x", retryable=True)), Step(text=["ok"], usage=Usage(5, 1))]
    )
    llm = ResilientLLM(provider, sleep=sleep)
    await collect(llm.stream(HELLO))
    assert (llm.counter.total, llm.counter.calls) == (6, 1)


# --- factory ---------------------------------------------------------------------------------


def settings(**values):
    return Settings(_env_file=None, **values)


def test_fake_is_default_in_dev_and_test(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)  # make exports .env into the environment
    assert settings().llm_provider == "fake"
    assert isinstance(get_llm_provider(settings(app_env="dev")), FakeLLM)
    assert isinstance(get_llm_provider(settings(app_env="test", llm_provider="stub")), FakeLLM)


def test_fake_is_rejected_in_prod():
    with pytest.raises(LLMNotConfigured):
        get_llm_provider(settings(app_env="prod", llm_provider="fake"))


def test_unknown_provider_gives_clear_error():
    with pytest.raises(LLMNotConfigured) as error:
        get_llm_provider(settings(llm_provider="anthropic"))
    assert "anthropic" in str(error.value)
    assert error.value.retryable is False


def test_resilient_factory_uses_config():
    llm = get_resilient_llm(settings(llm_timeout_sec=7, llm_max_retries=4))
    assert (llm.timeout_sec, llm.max_retries) == (7, 4)
