"""Ш-33 against fixture places in the database."""

from datetime import date
from uuid import UUID

import pytest

from app.planner import candidates, scoring
from app.planner.candidates import select_candidates
from app.planner.interests import resolve
from tests.test_places import add_place, load_categories

START, END = date(2026, 12, 5), date(2026, 12, 7)  # 3 days


def brief(**kw):
    values = {
        "start_date": START, "end_date": END, "budget_kzt": 500000,
        "has_accommodation": True, "must_haves": [], "interests": [],
        "pace": "normal", "crowd_tolerance": None,
    }  # fmt: skip
    values.update(kw)
    return values


async def fixture_places(conn):
    await load_categories(conn)
    ids = {}
    rows = [
        # name, lon, lat, category, popularity, status
        ("Медеу", 77.0587, 43.1573, "mountain", 90, "active"),
        ("Кок-Тобе", 76.9747, 43.2330, "viewpoint", 80, "active"),
        ("Музей искусств Кастеева", 76.9535, 43.2570, "museum", 70, "active"),
        ("Музей музыкальных инструментов", 76.9390, 43.2570, "museum", 40, "active"),
        ("Парк Горького", 76.9565, 43.2540, "park", 75, "active"),
        ("Монумент Независимости", 76.9450, 43.2380, "monument", 60, "active"),
        ("Чайхана Плов-центр", 76.9300, 43.2400, "cafe_oriental", 60, "active"),
        ("Дастархан", 76.9310, 43.2410, "cafe_kazakh", 50, "active"),
        ("Шанхай Дим-Сам", 76.9320, 43.2420, "cafe_chinese", 30, "active"),
        ("Кофейня Утро", 76.9330, 43.2430, "coffee", 20, "active"),
        ("Закрытый музей", 76.9400, 43.2500, "museum", 99, "closed"),
        ("Скрытый парк", 76.9400, 43.2510, "park", 99, "hidden"),
        ("Астанинский музей", 71.4300, 51.1280, "museum", 99, "active"),  # outside Almaty
        ("Отель Жол", 76.9500, 43.2500, "hotel", 99, "active"),  # lodging is Ш-35
    ]
    for name, lon, lat, category, popularity, status in rows:
        ids[name] = await add_place(conn, name, lon, lat, category, status, popularity)
    return ids


def names(items):
    return [c.place.name for c in items]


async def test_must_haves_become_places_by_category_and_by_name(conn):
    ids = await fixture_places(conn)
    sel = await select_candidates(
        conn, brief(must_haves=["Восточная кухня", "chinese food", "Медеу", "museums"])
    )
    by_text = {m.text: m for m in sel.must_haves}
    assert [p.id for p in by_text["Восточная кухня"].places] == [ids["Чайхана Плов-центр"]]
    assert by_text["Восточная кухня"].how == "category"
    assert [p.id for p in by_text["chinese food"].places] == [ids["Шанхай Дим-Сам"]]
    assert [p.id for p in by_text["Медеу"].places] == [ids["Медеу"]]
    assert by_text["Медеу"].how == "name"
    # a category wish gets 2 places on a 3-day trip, most popular first; closed/outside never
    assert [p.id for p in by_text["museums"].places] == [
        ids["Музей искусств Кастеева"],
        ids["Музей музыкальных инструментов"],
    ]
    assert sel.must_have_unmet == []
    for wish in sel.must_haves:
        assert wish.places  # every wish has at least one place


async def test_must_have_places_are_always_selected_and_not_repeated(conn):
    ids = await fixture_places(conn)
    sel = await select_candidates(conn, brief(must_haves=["Кофейня Утро", "кофе"]))
    must = {p.id for p in sel.must_have_places}
    assert ids["Кофейня Утро"] in must
    pooled = {c.place.id for c in sel.activities + sel.food}
    assert not (must & pooled)  # never twice
    # both wishes got the only coffee shop (shared when nothing else fits), nothing is dropped
    assert all(m.places for m in sel.must_haves)


async def test_unmet_must_have_is_reported_not_dropped(conn):
    await fixture_places(conn)
    sel = await select_candidates(conn, brief(must_haves=["корейская кухня", "каток", "Медеу"]))
    assert sel.must_have_unmet == ["корейская кухня", "каток"]
    assert [m.text for m in sel.must_haves] == ["корейская кухня", "каток", "Медеу"]
    assert [m.how for m in sel.must_haves] == ["none", "none", "name"]
    assert sel.must_haves[2].places  # the others are unaffected


async def test_only_active_almaty_non_lodging_places_are_candidates(conn):
    await fixture_places(conn)
    sel = await select_candidates(conn, brief())
    everything = set(names(sel.activities) + names(sel.food))
    assert not everything & {
        "Закрытый музей", "Скрытый парк", "Астанинский музей", "Отель Жол"
    }  # fmt: skip
    assert "Медеу" in everything and "Кофейня Утро" in everything
    assert set(names(sel.food)) == {
        "Чайхана Плов-центр", "Дастархан", "Шанхай Дим-Сам", "Кофейня Утро"
    }  # fmt: skip


async def test_interests_and_memory_change_the_order(conn):
    await fixture_places(conn)
    plain = await select_candidates(conn, brief())
    assert names(plain.activities)[0] == "Медеу"  # most popular
    museums = await select_candidates(conn, brief(interests=["музеи"]))
    assert names(museums.activities)[:2] == [
        "Музей искусств Кастеева",
        "Музей музыкальных инструментов",
    ]
    # museums the tourist removed before are shown less, not excluded
    shy = await select_candidates(conn, brief(interests=["музеи"]), memory={"museum": 1.0})
    assert "Музей искусств Кастеева" in names(shy.activities)  # lower, not excluded
    before = {c.place.name: c.score.total for c in museums.activities}
    after = {c.place.name: c.score.total for c in shy.activities}
    assert after["Музей искусств Кастеева"] == pytest.approx(
        before["Музей искусств Кастеева"] - scoring.W_MEMORY
    )
    assert after["Монумент Независимости"] == before["Монумент Независимости"]


async def test_crowd_source_is_used_for_quiet_travellers(conn):
    ids = await fixture_places(conn)

    class Busy:
        def level(self, place_id: UUID):
            return 1.0 if place_id == ids["Медеу"] else None

    quiet = await select_candidates(conn, brief(crowd_tolerance=0), crowd=Busy())
    relaxed = await select_candidates(conn, brief(crowd_tolerance=4), crowd=Busy())
    assert names(relaxed.activities)[0] == "Медеу"
    assert names(quiet.activities)[0] != "Медеу"
    assert "Медеу" in names(quiet.activities)  # lower, not removed


async def test_event_bonus_hook_is_applied(conn):
    ids = await fixture_places(conn)

    def bonus(place, start, end):
        assert (start, end) == (START, END)
        return 1.0 if place.id == ids["Монумент Независимости"] else 0.0

    sel = await select_candidates(conn, brief(interests=["events"]), event_bonus=bonus)
    top = sel.activities[0]
    assert top.place.name == "Монумент Независимости" or top.score.event == 0.0
    monument = next(c for c in sel.activities if c.place.id == ids["Монумент Независимости"])
    assert monument.score.event == 1.0


@pytest.mark.parametrize("pace, days, expected", [("calm", 1, 5), ("dense", 3, 27)])
async def test_pool_is_bounded_by_pace_and_days(conn, pace, days, expected):
    await fixture_places(conn)
    end = date(2026, 12, 4 + days)
    sel = await select_candidates(conn, brief(pace=pace, end_date=end))
    assert sel.pool.activities == expected
    assert len(sel.activities) <= expected and len(sel.food) <= sel.pool.food
    assert len(sel.activities) == min(expected, 6)  # the fixture has 6 non-food places in the area


async def test_incomplete_brief_is_refused(conn):
    with pytest.raises(ValueError):
        await select_candidates(conn, brief(start_date=None))
    with pytest.raises(ValueError):
        await select_candidates(conn, brief(end_date=date(2026, 12, 1)))


def test_must_have_count_grows_with_the_trip():
    assert [candidates.places_per_must_have(d) for d in (1, 2, 3, 5, 6, 30)] == [1, 1, 2, 2, 3, 3]
    assert scoring.pool_sizes(3, "normal").activities == 18
    assert resolve(["Медеу"]).empty
