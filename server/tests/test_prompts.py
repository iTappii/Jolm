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
    assert prompts.versions(prompts.GUEST, "en") == [1, 2]
    assert prompts.load_prompt(prompts.GUEST, "en", version=1).version == 1
    assert prompts.load_prompt(prompts.GUEST, "en").version == 2


def test_render_fills_today():
    text = prompts.load_prompt(prompts.TRIP_BRIEF, "en").render(date(2026, 12, 1))
    assert "2026-12-01" in text and "{{" not in text
    assert prompts.load_prompt(prompts.TRIP_BRIEF, "ru").render()


def test_trip_brief_asks_dates_then_budget_then_lodging():
    for locale, words in (
        ("en", ("dates", "tenge", "Lodging")),
        ("ru", ("Даты", "тенге", "Жильё")),
    ):
        text = prompts.load_prompt(prompts.TRIP_BRIEF, locale).text
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
