import json

import pytest

from app.chat import guest
from app.db import fetch_all, fetch_one
from app.providers.llm import FakeLLM, LLMError
from app.providers.llm.fake import FakeToolCall, Step
from app.ratelimit import RateRule
from tests.conftest import parse_sse
from tests.test_places import add_place

URL = "/v1/chat/guest"
HELLO = {"messages": [{"role": "user", "content": "Hi"}]}
INSTALL = "5B1F1E1E-9F0F-4B4B-8B0C-0E5E5E5E5E5E"


def use(env, **kwargs):
    llm = FakeLLM(**kwargs)
    env.app.state.llm_provider = llm
    return llm


async def post(env, body=None, headers=None):
    return await env.client.post(URL, json=HELLO if body is None else body, headers=headers or {})


async def test_stream_order_and_framing(chat_env):
    use(chat_env, steps=[Step(text=["Hel", "lo"])])
    response = await post(chat_env)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["text_delta", "text_delta", "done"]
    assert [d["text"] for n, d in events if n == "text_delta"] == ["Hel", "lo"]
    usage = events[-1][1]["usage"]
    assert usage["input_tokens"] > 0 and usage["output_tokens"] > 0


async def test_tool_call_searches_places_and_the_answer_continues(chat_env, conn):
    await add_place(conn, "Кок-Тобе", 76.97, 43.23)
    llm = use(
        chat_env,
        steps=[
            Step(
                text=["Let me check. "],
                tool_calls=[FakeToolCall("search_places", {"query": "Кок"})],
            ),
            Step(text=["Kok-Tobe is a hill."]),
        ],
    )
    events = parse_sse((await post(chat_env, {**HELLO, "locale": "ru"})).text)
    assert [n for n, _ in events] == ["text_delta", "map_places", "text_delta", "done"]
    pins = events[1][1]
    assert pins["reason"] == "search"
    assert [p["name"] for p in pins["places"]] == ["Кок-Тобе"]
    assert set(pins["places"][0]) == {"id", "name", "category", "lat", "lon"}
    assert len(llm.calls) == 2
    # the model sees the tool result and keeps having the tool
    last = llm.calls[1].messages
    assert last[-2].role == "assistant" and last[-2].tool_calls[0].name == "search_places"
    assert last[-1].role == "tool" and "Кок-Тобе" in last[-1].content
    assert llm.calls[1].tools and llm.calls[1].tools[0].name == "search_places"
    # the guest prompt (no trip tools), in the requested language
    assert "Today is" not in llm.calls[0].system and "Сегодня" in llm.calls[0].system
    assert [t.name for t in llm.calls[0].tools] == ["search_places", "search_events"]


async def test_nothing_found_is_not_pinned(chat_env):
    llm = use(
        chat_env,
        steps=[
            Step(tool_calls=[FakeToolCall("search_places", {"query": "zzzz"})]),
            Step(text=["Do not know."]),
        ],
    )
    events = parse_sse((await post(chat_env)).text)
    assert [n for n, _ in events] == ["text_delta", "done"]
    assert json.loads(llm.calls[1].messages[-1].content) == {"places": [], "note": "nothing found"}


@pytest.mark.parametrize(
    "arguments",
    [{"query": "x" * 101}, {"limit": 99, "query": "park"}, "not json", {"query": "a"}, {}],
    ids=["long", "limit", "malformed", "short", "empty"],
)
async def test_bad_tool_arguments_come_back_as_a_tool_error(chat_env, arguments):
    llm = use(
        chat_env,
        steps=[Step(tool_calls=[FakeToolCall("search_places", arguments)]), Step(text=["ok"])],
    )
    response = await post(chat_env)
    assert response.status_code == 200
    assert [n for n, _ in parse_sse(response.text)] == ["text_delta", "done"]
    assert "error" in json.loads(llm.calls[1].messages[-1].content)


async def test_unknown_tool_is_reported_to_the_model(chat_env):
    llm = use(
        chat_env,
        steps=[Step(tool_calls=[FakeToolCall("update_trip_brief", {})]), Step(text=["ok"])],
    )
    assert (await post(chat_env)).status_code == 200
    assert "unknown tool" in llm.calls[1].messages[-1].content


async def test_tool_rounds_are_capped(chat_env):
    llm = use(chat_env, steps=[Step(tool_calls=[FakeToolCall("search_places", {"query": "park"})])])
    events = parse_sse((await post(chat_env)).text)
    assert len(llm.calls) == guest.MAX_TOOL_ROUNDS + 1
    assert llm.calls[-1].tools is None  # the last call must answer without tools
    assert events[-1][0] == "done"


@pytest.mark.parametrize(
    "body",
    [
        {"messages": []},
        {},
        {"messages": [{"role": "user", "content": ""}]},
        {"messages": [{"role": "user", "content": "   "}]},
        {"messages": [{"role": "system", "content": "x"}]},
        {"messages": [{"role": "user", "content": "x" * (guest.MAX_MESSAGE_CHARS + 1)}]},
        {"messages": [{"role": "user", "content": "x"}] * (guest.MAX_MESSAGES + 1)},
        {"messages": [{"role": "user", "content": "x" * 2000}] * 5},  # 10000 > total limit
        {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]},
        {**HELLO, "locale": "de"},
    ],
    ids=[
        "empty",
        "missing",
        "blank",
        "spaces",
        "role",
        "long-message",
        "too-many",
        "total",
        "last-not-user",
        "locale",
    ],
)
async def test_history_limits_are_422(chat_env, body):
    llm = use(chat_env)
    response = await post(chat_env, body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert llm.calls == []


async def test_history_at_the_limits_is_accepted(chat_env):
    use(chat_env)
    turns = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": "x" * 400} for i in range(19)
    ]
    assert len(turns) == 19 and sum(len(t["content"]) for t in turns) <= guest.MAX_TOTAL_CHARS
    assert (await post(chat_env, {"messages": turns})).status_code == 200


async def test_rate_limit_by_install_id(chat_env):
    use(chat_env)
    limiters = chat_env.app.state.chat_limiters
    limiters.guest_install = RateRule("t", 2, 3600)
    headers = {"X-Install-ID": INSTALL}
    assert (await post(chat_env, headers=headers)).status_code == 200
    assert (await post(chat_env, headers=headers)).status_code == 200
    blocked = await post(chat_env, headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) > 0
    # another installation (same IP) still works
    other = {"X-Install-ID": "11111111-2222-3333-4444-555555555555"}
    assert (await post(chat_env, headers=other)).status_code == 200
    # the id is case-insensitive
    assert (await post(chat_env, headers={"X-Install-ID": INSTALL.lower()})).status_code == 429


@pytest.mark.parametrize("header", [{}, {"X-Install-ID": "not-a-uuid"}, {"X-Install-ID": ""}])
async def test_rate_limit_by_ip_when_install_id_missing_or_invalid(chat_env, header):
    use(chat_env)
    chat_env.app.state.chat_limiters.guest_ip = RateRule("t", 2, 3600)
    assert (await post(chat_env, headers=header)).status_code == 200
    assert (await post(chat_env, headers=header)).status_code == 200
    assert (await post(chat_env, headers=header)).status_code == 429


async def test_ip_limit_also_stops_rotating_install_ids(chat_env):
    use(chat_env)
    chat_env.app.state.chat_limiters.guest_ip = RateRule("t", 2, 3600)
    ids = ["00000000-0000-4000-8000-00000000000%d" % i for i in range(3)]
    codes = [(await post(chat_env, headers={"X-Install-ID": i})).status_code for i in ids]
    assert codes == [200, 200, 429]


async def test_rejected_requests_do_not_consume_the_limit(chat_env):
    use(chat_env)
    chat_env.app.state.chat_limiters.guest_install = RateRule("t", 1, 3600)
    headers = {"X-Install-ID": INSTALL}
    assert (await post(chat_env, {"messages": []}, headers)).status_code == 422
    assert (await post(chat_env, headers=headers)).status_code == 200


async def test_guest_chat_writes_nothing_to_the_database(chat_env, conn):
    await add_place(conn, "Кок-Тобе", 76.97, 43.23)
    tables = [
        r["tablename"]
        for r in await fetch_all(
            conn, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
    ]
    assert "chats" in tables and "otp_codes" in tables
    # shared rate-limit counters (Ш-51) are bookkeeping, not chat data: hashed key + timestamps
    # rate limits and daily token counters hold only hashed keys and numbers, never chat content
    tables = [t for t in tables if t not in ("rate_limit_hits", "llm_usage_daily")]

    async def snapshot():
        rows = {}
        for table in tables:
            row = await fetch_one(conn, 'SELECT count(*) AS n FROM "%s"' % table)  # noqa: S608
            rows[table] = row["n"]
        return rows

    use(
        chat_env,
        steps=[
            Step(tool_calls=[FakeToolCall("search_places", {"query": "Кок"})]),
            Step(text=["Done."]),
        ],
    )
    before = await snapshot()
    headers = {"X-Install-ID": INSTALL}
    assert (await post(chat_env, headers=headers)).status_code == 200
    assert (await post(chat_env, {"messages": []}, headers)).status_code == 422
    assert await snapshot() == before


async def test_provider_failure_ends_with_an_error_event(chat_env):
    use(chat_env, steps=[Step(error=LLMError("llm_boom", "secret detail"))])
    response = await post(chat_env, {**HELLO, "locale": "ru"})
    assert response.status_code == 200
    events = parse_sse(response.text)
    assert [n for n, _ in events] == ["error"]
    assert events[0][1] == {"code": "llm_error", "message": "Ассистент не смог ответить"}
    assert "secret" not in response.text


async def test_failure_after_text_keeps_the_text_and_sends_no_done(chat_env):
    use(chat_env, steps=[Step(text=["Part"], error_after=LLMError("llm_timeout", "slow"))])
    events = parse_sse((await post(chat_env)).text)
    assert [n for n, _ in events] == ["text_delta", "error"]
    assert events[1][1]["code"] == "llm_timeout"


async def test_provider_not_configured_is_503_before_streaming(chat_env, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "llm_provider", "openai")
    response = await post(chat_env)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_unavailable"


async def test_token_usage_is_per_request(chat_env):
    use(chat_env, steps=[Step(text=["Hi"])])
    first = parse_sse((await post(chat_env)).text)[-1][1]["usage"]
    second = parse_sse((await post(chat_env)).text)[-1][1]["usage"]
    assert first == second  # a shared counter would double the second one


async def test_locale_falls_back_to_accept_language(chat_env):
    llm = use(chat_env)
    await post(chat_env, headers={"Accept-Language": "ru"})
    assert "Сегодня" in llm.calls[0].system
    await post(chat_env)
    assert "Today is" in llm.calls[1].system
