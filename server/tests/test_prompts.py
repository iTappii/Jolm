from datetime import date

import pytest

from app.chat import prompts


@pytest.mark.parametrize("name", [prompts.TRIP_BRIEF, prompts.GUEST])
@pytest.mark.parametrize("locale", ["ru", "en"])
def test_every_prompt_exists_in_both_languages(name, locale):
    prompt = prompts.load_prompt(name, locale)
    assert prompt.locale == locale and prompt.version >= 1
    assert prompt.id == f"{name}.{locale}.v{prompt.version}"
    assert "<!--" not in prompt.text and prompt.text


def test_unknown_locale_falls_back_to_english_and_unknown_prompt_fails():
    assert prompts.load_prompt(prompts.GUEST, "kk").locale == "en"
    with pytest.raises(LookupError):
        prompts.load_prompt("nope", "en")
    with pytest.raises(LookupError):
        prompts.load_prompt(prompts.GUEST, "en", version=99)


def test_versions_are_listed_and_latest_is_loaded():
    assert prompts.versions(prompts.GUEST, "en") == [1, 2, 3, 4, 5]
    assert prompts.load_prompt(prompts.GUEST, "en", version=1).version == 1
    assert prompts.load_prompt(prompts.GUEST, "en").version == 5


def test_render_fills_today():
    text = prompts.load_prompt(prompts.TRIP_BRIEF, "en").render(date(2026, 12, 1))
    assert "2026-12-01" in text and "{{" not in text
    assert prompts.load_prompt(prompts.TRIP_BRIEF, "ru").render()


def test_trip_brief_asks_dates_then_budget_then_lodging():
    for locale, words in (
        ("en", ("dates", "KZT", "Lodging")),
        ("ru", ("Даты", "KZT", "Жильё")),
    ):
        text = prompts.load_prompt(prompts.TRIP_BRIEF, locale).render()
        positions = [text.index(word) for word in words]
        assert positions == sorted(positions)
        for tool in ("update_trip_brief", "add_graph_node", "search_places", "build_trip"):
            assert tool in text


def test_guest_prompt_exposes_place_and_event_search():
    for locale in ("en", "ru"):
        text = prompts.load_prompt(prompts.GUEST, locale).text
        assert all(word in text for word in ("search_places", "search_events", "ad_label"))
        for tool in ("update_trip_brief", "build_trip", "add_graph_node"):
            assert tool not in text


def test_latest_prompts_name_places_outside_the_area_honestly():  # Ш-56
    for name in (prompts.TRIP_BRIEF, prompts.GUEST):
        for locale in ("en", "ru"):
            assert "outside_area" in prompts.load_prompt(name, locale).text


def test_latest_prompts_take_city_and_currency_from_the_region():  # Ш-57
    from app.regions import default_region

    region = default_region()
    for name in (prompts.TRIP_BRIEF, prompts.GUEST):
        for locale in ("en", "ru"):
            prompt = prompts.load_prompt(name, locale)
            assert "{{region}}" in prompt.text  # nothing city-specific in the file itself
            assert "Almaty" not in prompt.text and "Алматы" not in prompt.text
            rendered = prompt.render()
            assert region.name(locale) in rendered and "{{" not in rendered
    brief = prompts.load_prompt(prompts.TRIP_BRIEF, "en")
    assert "{{currency}}" in brief.text and region.currency in brief.render()
    other = default_region().__class__(
        id="x", name_ru="Икс", name_en="Ex", timezone="UTC", currency="USD",
        languages=("en",), centre=(0.0, 0.0), zoom=5.0, bbox=(0.0, 0.0, 1.0, 1.0),
    )  # fmt: skip
    text = brief.render(region=other)
    assert "Ex," in text and "USD" in text and "KZT" not in text


# --- Ш-66: boundaries of the assistant ---------------------------------------------------------
BOUNDARY_WORDS = {
    "en": ("Allowed", "Not allowed", "code", "SQL", "tool names", "data, not commands", "Examples"),
    "ru": ("Можно", "Нельзя", "код", "SQL", "названия и аргументы инструментов",
           "данные, а не команды", "Примеры"),
}  # fmt: skip


def test_prompt_v9_and_v5_carry_the_boundaries_and_are_the_ones_in_use():
    for name, version, previous in ((prompts.TRIP_BRIEF, 9, 8), (prompts.GUEST, 5, 4)):
        for locale in ("en", "ru"):
            latest = prompts.load_prompt(name, locale)
            assert latest.version == version  # the app loads the highest version (see deps/api)
            for word in BOUNDARY_WORDS[locale]:
                assert word in latest.text, (name, locale, word)
            old = prompts.load_prompt(name, locale, version=previous).text
            assert "SQL" not in old  # the released version is untouched
            assert "Stay on topic" not in latest.text and "Держись темы" not in latest.text


def test_boundaries_do_not_name_internal_tools_in_the_guest_prompt():
    for locale in ("en", "ru"):
        text = prompts.load_prompt(prompts.GUEST, locale).text
        for tool in ("update_trip_brief", "build_trip", "add_graph_node"):
            assert tool not in text


async def test_the_chats_use_the_latest_prompts(chat_env, conn):
    from app.providers.llm import FakeLLM
    from app.providers.llm.fake import Step
    from tests.test_chat import new_chat, say, sign_in

    llm = FakeLLM(steps=[Step(text=["ok"])])
    chat_env.app.state.llm_provider = llm
    headers = await sign_in(conn)
    chat = await new_chat(chat_env, headers, "en")
    assert (await say(chat_env, headers, chat["id"])).status_code == 200
    assert "Boundaries" in llm.calls[0].system
    guest = await chat_env.client.post(
        "/v1/chat/guest", json={"messages": [{"role": "user", "content": "Hi"}], "locale": "ru"}
    )
    assert guest.status_code == 200
    assert "Рамки" in llm.calls[-1].system
