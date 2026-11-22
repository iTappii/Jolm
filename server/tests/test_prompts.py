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
    assert prompts.versions(prompts.GUEST, "en") == [1, 2, 3, 4]
    assert prompts.load_prompt(prompts.GUEST, "en", version=1).version == 1
    assert prompts.load_prompt(prompts.GUEST, "en").version == 4


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
