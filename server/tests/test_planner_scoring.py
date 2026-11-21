"""Pure planner logic: keyword reading, scoring, pool sizes. No database."""

from datetime import date
from uuid import UUID, uuid4

import pytest

from app.planner import scoring
from app.planner.interests import Resolved, resolve
from app.planner.model import Place
from app.planner.signals import UnknownCrowd, no_event_bonus

NONE = Resolved(frozenset(), False, False)


def make_place(category="museum", parent="culture", popularity=50, setting="indoor", **kw):
    values = dict(
        id=uuid4(), name_ru="Место", name_en=None, category=category, parent=parent,
        kind="venue", setting=setting, outdoor=False, lat=43.2, lon=76.9,
        popularity=popularity, is_public=False, is_mountain=False, typical_visit_min=None,
        entry_price_kzt=None, avg_check_kzt=None,
    )  # fmt: skip
    values.update(kw)
    return Place(**values)


def total(place, profile=NONE, memory=None, crowd=None, tolerance=None, event=0.0):
    return scoring.score_place(place, profile, memory or {}, crowd, tolerance, event)


# --- reading free text ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, slugs",
    [
        ("восточная кухня", {"cafe_oriental"}),
        ("Chinese food", {"cafe_chinese"}),
        ("китайская еда", {"cafe_chinese"}),
        ("плов", {"cafe_oriental", "cafe_kazakh"}),
        ("Museums", {"museum"}),
        ("музеи и выставки", {"museum", "gallery"}),
        ("sushi", {"cafe_japanese"}),
        ("food", {"food"}),
        ("Медеу", set()),  # a name, not a category
        ("большой город", set()),  # "горы" must not match "город"
        ("barcelona", set()),  # "bar" is a whole word only
    ],
)
def test_resolve_slugs(text, slugs):
    assert resolve([text]).slugs == slugs


def test_resolve_flags_and_empty_input():
    assert resolve(["hiking in the mountains"]).outdoor is True
    assert resolve(["фестивали"]).events is True
    assert resolve([]).empty and resolve(["quiet"]).empty


# --- scoring -------------------------------------------------------------------------------


def test_popularity_alone_orders_places():
    low, high = make_place(popularity=10), make_place(popularity=90)
    assert total(high).total > total(low).total
    assert total(high).total == pytest.approx(scoring.W_POPULARITY * 0.9)


def test_popularity_is_clipped():
    assert total(make_place(popularity=500)).popularity == 1.0
    assert total(make_place(popularity=-5)).popularity == 0.0


def test_interest_match_exact_group_and_none():
    profile = resolve(["museums"])
    assert scoring.interest_match(make_place("museum", "culture"), profile) == 1.0
    group = resolve(["культура"])  # no keyword: nothing matches
    assert scoring.interest_match(make_place("museum", "culture"), group) == 0.0
    food = resolve(["food"])
    assert scoring.interest_match(make_place("coffee", "food"), food) == scoring.GROUP_MATCH
    assert scoring.interest_match(make_place("park", "nature"), profile) == 0.0


def test_outdoor_interest_prefers_outdoor_places():
    profile = resolve(["outdoors"])
    park = make_place("park", "nature", setting="outdoor")
    museum = make_place("museum", "culture")
    assert total(park, profile).interest > total(museum, profile).interest == 0.0


def test_an_interest_match_beats_a_little_popularity():
    profile = resolve(["museums"])
    match = make_place("museum", popularity=20)
    famous = make_place("monument", "sights", popularity=80)
    assert total(match, profile).total > total(famous, profile).total


def test_memory_penalty_lowers_but_does_not_exclude():
    place = make_place("museum", "culture", popularity=60)
    plain = total(place).total
    assert total(place, memory={"museum": 1.0}).total == pytest.approx(plain - scoring.W_MEMORY)
    half = total(place, memory={"culture": 0.5}).total  # a whole group can be penalized too
    assert half == pytest.approx(plain - 0.5 * scoring.W_MEMORY)
    assert total(place, memory={"museum": 9}).memory == 1.0  # clipped
    assert total(place, memory={"park": 1.0}).total == plain  # other types are unaffected


def test_crowd_penalty_scales_with_intolerance():
    place = make_place(popularity=50)
    base = total(place).total
    quiet = total(place, crowd=1.0, tolerance=0).total  # only quiet places
    fine = total(place, crowd=1.0, tolerance=4).total  # fine in a crowd
    middle = total(place, crowd=1.0, tolerance=2).total
    assert quiet == pytest.approx(base - scoring.W_CROWD)
    assert fine == pytest.approx(base)
    assert middle == pytest.approx(base - scoring.W_CROWD / 2)
    assert total(place, crowd=None, tolerance=0).total == base  # unknown crowd costs nothing
    assert total(place, crowd=1.0, tolerance=None).total == middle  # default tolerance


def test_event_bonus_counts_double_when_asked():
    place = make_place(popularity=0)
    plain = total(place, event=1.0).total
    asked = total(place, resolve(["festivals"]), event=1.0).total
    assert plain == pytest.approx(scoring.W_EVENT * scoring.EVENT_UNASKED_FACTOR)
    assert asked == pytest.approx(scoring.W_EVENT)
    assert total(place, event=7.0).event == 1.0  # clipped


def test_default_hooks_mean_no_data():
    assert UnknownCrowd().level(uuid4()) is None
    assert no_event_bonus(make_place(), date(2026, 12, 1), date(2026, 12, 3)) == 0.0


# --- pool sizes and picking ----------------------------------------------------------------


@pytest.mark.parametrize(
    "days, pace, activities, food",
    [
        (3, "normal", 18, 9),
        (3, None, 18, 9),
        (3, "calm", 14, 9),
        (3, "dense", 27, 9),
        (1, "calm", 5, 3),
        (7, "dense", 63, 21),
        (60, "dense", scoring.MAX_ACTIVITY_POOL, scoring.MAX_FOOD_POOL),
    ],
)
def test_pool_sizes(days, pace, activities, food):
    assert scoring.pool_sizes(days, pace) == scoring.PoolSizes(activities, food)


def test_a_longer_trip_or_denser_pace_never_shrinks_the_pool():
    for pace in ("calm", "normal", "dense"):
        sizes = [scoring.pool_sizes(d, pace).activities for d in range(1, 20)]
        assert sizes == sorted(sizes)
    for days in (1, 5, 12):
        a = [scoring.pool_sizes(days, p).activities for p in ("calm", "normal", "dense")]
        assert a == sorted(a)


def scored(place, **kw):
    return scoring.Scored(place, total(place, **kw))


def test_rank_is_deterministic_and_breaks_ties_by_popularity_then_id():
    ids = [UUID(int=i) for i in (3, 1, 2)]
    a = make_place(popularity=0, id=ids[0])
    b = make_place(popularity=0, id=ids[1])
    c = make_place(popularity=0, id=ids[2])
    order = [s.place.id for s in scoring.rank([scored(a), scored(b), scored(c)])]
    assert order == sorted(ids)
    assert order == [s.place.id for s in scoring.rank([scored(c), scored(a), scored(b)])]


def test_pick_pool_caps_one_category_skips_taken_and_respects_size():
    monuments = [make_place("monument", "sights", popularity=90 - i) for i in range(10)]
    others = [make_place("park", "nature", popularity=10 + i) for i in range(4)]
    items = [scored(p) for p in monuments + others]
    pool = scoring.pick_pool(items, 4)  # cap = ceil(4 * 0.4) = 2 per category
    assert sorted(s.place.category for s in pool) == ["monument", "monument", "park", "park"]
    assert len(scoring.pick_pool(items, 8)) == 8  # not enough variety: capped-out places fill in
    pool = scoring.pick_pool(items, 5)
    taken = {monuments[0].id}
    pool = scoring.pick_pool(items, 5, taken)
    assert monuments[0].id not in {s.place.id for s in pool}
    assert scoring.pick_pool(items, 0) == []
