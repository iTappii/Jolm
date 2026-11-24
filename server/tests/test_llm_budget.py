"""Ш-66: output cap and daily token budgets (user, guest, whole service)."""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr

from app import llm_budget, metrics
from app.chat.engine import ToolOutcome, TurnRecord, run_turn
from app.config import get_settings
from app.db import fetch_one
from app.providers.llm import FakeLLM, Message, ResilientLLM
from app.providers.llm.fake import FakeToolCall, Step
from tests.conftest import parse_sse
from tests.test_chat import new_chat, say, sign_in
from tests.test_chat import use as use_chat

GUEST = "/v1/chat/guest"
HELLO = {"messages": [{"role": "user", "content": "Hi"}]}
INSTALL = "5B1F1E1E-9F0F-4B4B-8B0C-0E5E5E5E5E5E"
OTHER_INSTALL = "6C2F2F2F-9F0F-4B4B-8B0C-0E5E5E5E5E5E"


@pytest.fixture(autouse=True)
async def secrets(monkeypatch, conn):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    metrics.reset()
    # tests that commit (test_chat_background) leave counters behind; this one is rolled back
    await conn.execute("DELETE FROM llm_usage_daily")


def limits(monkeypatch, **values):
    base = dict(
        llm_daily_tokens_user=0,
        llm_daily_tokens_guest_install=0,
        llm_daily_tokens_guest_ip=0,
        llm_daily_tokens_global=0,
    )
    for name, value in {**base, **values}.items():
        monkeypatch.setattr(get_settings(), name, value)


async def guest(env, install=INSTALL, body=None):
    headers = {"X-Install-ID": install} if install else {}
    return await env.client.post(GUEST, json=body or HELLO, headers=headers)


# --- the output cap ----------------------------------------------------------------------------


async def test_chat_replies_carry_the_output_cap(chat_env, conn, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_max_output_tokens", 321)
    llm = use_chat(chat_env, steps=[Step(text=["hi"])])
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    assert (await say(chat_env, headers, chat["id"])).status_code == 200
    assert (await guest(chat_env)).status_code == 200
    assert [c.max_tokens for c in llm.calls] == [321, 321]


async def test_plan_explanation_round_gets_the_larger_cap():
    llm = FakeLLM(steps=[Step(tool_calls=[FakeToolCall("build_trip", {})]), Step(text=["plan"])])
    resilient = ResilientLLM(llm, max_output_tokens=100, max_output_tokens_plan=500)

    async def handle(call):
        return ToolOutcome({"ok": True})

    record = TurnRecord()
    async for _ in run_turn(resilient, [Message(role="user", content="go")], [], "s", handle,
                            record, "en", 3):  # fmt: skip
        pass
    assert [c.max_tokens for c in llm.calls] == [100, 500]


async def test_reply_cut_by_the_cap_ends_cleanly(chat_env, conn, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_max_output_tokens", 2)  # 8 characters
    use_chat(chat_env, steps=[Step(text=["Hello ", "wonderful ", "world"])])
    events = parse_sse((await guest(chat_env)).text)
    names = [n for n, _ in events]
    assert names[-1] == "done" and "error" not in names
    assert "".join(d["text"] for n, d in events if n == "text_delta") == "Hello wo"
    assert "jol_llm_truncated_total 1" in metrics.render()
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    reply = await say(chat_env, headers, chat["id"])
    assert parse_sse(reply.text)[-1][0] == "done"
    row = await fetch_one(conn, "SELECT content, finish FROM chat_messages WHERE role='assistant'")
    assert row["content"] == "Hello wo" and row["finish"] == "stop"


# --- per-user budget ---------------------------------------------------------------------------


async def test_user_budget_blocks_before_the_model_and_resets_next_day(chat_env, conn, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_user=100)
    llm = use_chat(chat_env, steps=[Step(text=["ok"])])
    a = await sign_in(conn, "a@example.com")
    b = await sign_in(conn, "b@example.com", "ru")
    chat_a = await new_chat(chat_env, a)
    chat_b = await new_chat(chat_env, b, "ru")
    assert (await say(chat_env, a, chat_a["id"])).status_code == 200  # a turn costs > 100
    calls = len(llm.calls)
    blocked = await say(chat_env, a, chat_a["id"])
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "llm_budget_exceeded"
    assert "limit" in blocked.json()["error"]["message"]
    assert int(blocked.headers["retry-after"]) > 0
    assert len(llm.calls) == calls  # the model was not called
    ru = await say(chat_env, b, chat_b["id"])  # another user is not affected
    assert ru.status_code == 200
    blocked_ru = await say(chat_env, {**b, "Accept-Language": "ru"}, chat_b["id"])
    assert blocked_ru.status_code == 429
    assert "лимит" in blocked_ru.json()["error"]["message"]
    # the next regional day: counters start from zero
    tomorrow = llm_budget.budget_day() + timedelta(days=1)
    monkeypatch.setattr(llm_budget, "budget_day", lambda now=None: tomorrow)
    assert (await say(chat_env, a, chat_a["id"])).status_code == 200


async def test_blocked_user_message_is_not_stored(chat_env, conn, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_user=1)
    use_chat(chat_env, steps=[Step(text=["ok"])])
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    assert (await say(chat_env, headers, chat["id"])).status_code == 200
    before = await fetch_one(conn, "SELECT count(*) AS n FROM chat_messages")
    assert (await say(chat_env, headers, chat["id"], "again")).status_code == 429
    after = await fetch_one(conn, "SELECT count(*) AS n FROM chat_messages")
    assert before["n"] == after["n"]
    lease = await fetch_one(conn, "SELECT turn_lease_until FROM chats")
    assert not lease["turn_lease_until"] or lease["turn_lease_until"] <= datetime.now(timezone.utc)


# --- guest budgets -----------------------------------------------------------------------------


async def test_guest_install_budget(chat_env, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_guest_install=100)
    llm = use_chat(chat_env, steps=[Step(text=["ok"])])
    assert (await guest(chat_env)).status_code == 200
    calls = len(llm.calls)
    blocked = await guest(chat_env)
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "llm_budget_exceeded"
    assert len(llm.calls) == calls
    assert (await guest(chat_env, OTHER_INSTALL)).status_code == 200  # another install
    tomorrow = llm_budget.budget_day() + timedelta(days=1)
    monkeypatch.setattr(llm_budget, "budget_day", lambda now=None: tomorrow)
    assert (await guest(chat_env)).status_code == 200


async def test_guest_ip_budget_covers_installs_and_anonymous_requests(chat_env, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_guest_ip=100)
    use_chat(chat_env, steps=[Step(text=["ok"])])
    assert (await guest(chat_env)).status_code == 200
    assert (await guest(chat_env, OTHER_INSTALL)).status_code == 429  # same IP
    assert (await guest(chat_env, install=None)).status_code == 429


async def test_guest_counters_hold_no_raw_identifiers(chat_env, conn, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_guest_install=10**6)
    use_chat(chat_env, steps=[Step(text=["ok"])])
    assert (await guest(chat_env)).status_code == 200
    from app.db import fetch_all

    rows = await fetch_all(conn, "SELECT key_hash FROM llm_usage_daily")
    assert rows and all(len(r["key_hash"]) == 64 for r in rows)
    assert not any(INSTALL.lower() in r["key_hash"] for r in rows)


# --- global budget -----------------------------------------------------------------------------


async def test_global_budget_refuses_everyone_with_503(chat_env, conn, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_global=100)
    llm = use_chat(chat_env, steps=[Step(text=["ok"])])
    assert (await guest(chat_env)).status_code == 200
    calls = len(llm.calls)
    refused = await guest(chat_env, OTHER_INSTALL)
    assert refused.status_code == 503
    assert refused.json()["error"]["code"] == "llm_budget_service"
    assert int(refused.headers["retry-after"]) > 0
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers)
    registered = await say(chat_env, headers, chat["id"])
    assert registered.status_code == 503
    assert registered.json()["error"]["code"] == "llm_budget_service"
    assert len(llm.calls) == calls


async def test_zero_means_no_limit(chat_env, monkeypatch):
    limits(monkeypatch)
    use_chat(chat_env, steps=[Step(text=["ok"])])
    for _ in range(3):
        assert (await guest(chat_env)).status_code == 200


async def test_global_thresholds_warn_once_and_show_in_metrics(conn, monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_budget_warn_percent", 80)
    budgets = [llm_budget.global_budget(settings.__class__(llm_daily_tokens_global=1000))]
    caplog.set_level(logging.WARNING, logger="app.llm_budget")
    await llm_budget.record(conn, budgets, 700, settings)
    assert "budget at" not in caplog.text
    await llm_budget.record(conn, budgets, 150, settings)  # 850 >= 800: 80%
    assert "at 80%" in caplog.text and "at 100%" not in caplog.text
    await llm_budget.record(conn, budgets, 10, settings)  # still past 80%: no second warning
    assert caplog.text.count("at 80%") == 1
    await llm_budget.record(conn, budgets, 200, settings)  # 1060: 100%
    assert "at 100%" in caplog.text
    text = metrics.render()
    assert 'jol_llm_budget_threshold_total{percent="80"} 1' in text
    assert 'jol_llm_budget_threshold_total{percent="100"} 1' in text
    assert await llm_budget.global_used_today(conn) == 1060


async def test_metrics_endpoint_shows_the_global_gauges(chat_env, monkeypatch):
    limits(monkeypatch, llm_daily_tokens_global=10**9)
    use_chat(chat_env, steps=[Step(text=["ok"])])
    assert (await guest(chat_env)).status_code == 200
    text = (await chat_env.client.get("/metrics")).text
    assert "jol_llm_tokens_budget 1000000000" in text
    used = [x for x in text.splitlines() if x.startswith("jol_llm_tokens_today ")]
    assert used and int(used[0].split()[1]) > 0


async def test_day_boundary_is_the_regional_midnight(conn):
    # 2026-12-01 20:00 UTC is already 2026-12-02 01:00 in Asia/Almaty (UTC+5)
    now = datetime(2026, 12, 1, 20, 0, tzinfo=timezone.utc)
    assert llm_budget.budget_day(now).isoformat() == "2026-12-02"
    assert llm_budget.seconds_until_next_day(now) == 23 * 3600 + 1
    settings = get_settings()
    budgets = [llm_budget.Budget("user", "u1", 50)]
    await llm_budget.record(conn, budgets, 60, settings, now)
    with pytest.raises(Exception) as err:
        await llm_budget.check(conn, budgets, now)
    assert err.value.code == "llm_budget_exceeded"
    later = now + timedelta(hours=23)  # the next regional day
    await llm_budget.check(conn, budgets, later)
    assert await llm_budget.cleanup(conn, later + timedelta(days=10)) == 1
