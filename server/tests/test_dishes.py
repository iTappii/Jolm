"""Search by dish (Ш-67): dictionary resolution, cuisine ranking, `near`, guest and live route."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.chat import live_route, tools
from app.places import dishes, recommend
from app.providers.llm.fake import FakeToolCall, Step
from tests.conftest import parse_sse
from tests.test_places import add_place, load_categories

SEED = Path(__file__).resolve().parents[2] / "data" / "seed" / "dishes.sql"
GREEN_BAZAAR = (76.9539, 43.2614)  # lon, lat
INSTALL = "5B1F1E1E-9F0F-4B4B-8B0C-0E5E5E5E5E5E"


class Db:
    """The `db.transaction()` the tools expect, over the test connection."""

    def __init__(self, conn):
        self.conn = conn

    def transaction(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


async def seed(conn):
    await load_categories(conn)
    await conn.execute(SEED.read_text(encoding="utf-8"))
    ids = {}
    for name, lon, lat, cat, pop in [
        ("Зелёный базар", *GREEN_BAZAAR, "market", 90),
        ("Жайлау", 76.9560, 43.2630, "cafe_kazakh", 40),  # ~250 m from the bazaar
        ("Дастархан", 76.9600, 43.2640, "cafe_kazakh", 60),  # ~600 m
        ("Чайхана Нават", 76.9570, 43.2600, "cafe_oriental", 80),  # related cuisine, close
        ("Қазақ асханасы далеко", 77.1000, 43.1500, "cafe_kazakh", 99),  # far (> 10 km)
        ("Dragon Wok", 76.9540, 43.2620, "cafe_chinese", 70),
        ("Тихий парк", 76.9545, 43.2610, "park", 50),
    ]:
        ids[name] = await add_place(conn, name, lon, lat, cat, "active", pop)
    return ids


@pytest.fixture
async def world(conn):
    ids = await seed(conn)
    return SimpleNamespace(conn=conn, db=Db(conn), ids=ids)


def names(result):
    return [p["name"] for p in result["places"]]


# ---------------------------------------------------------------- dictionary resolution


@pytest.mark.parametrize(
    "query, slug",
    [
        ("бешбармак", "beshbarmak"),
        ("Бешбармак", "beshbarmak"),
        ("БЕШБАРМАК!", "beshbarmak"),
        ("beshbarmak", "beshbarmak"),
        ("Besbarmak", "beshbarmak"),
        ("бесбармак", "beshbarmak"),
        ("бешбармақ", "beshbarmak"),
        ("бишбармак", "beshbarmak"),  # alias typo
        ("бешбармк", "beshbarmak"),  # fuzzy: a letter missing
        ("где поесть бешбармак", "beshbarmak"),
        ("plov", "plov"),
        ("Pilaf", "plov"),
        ("палау", "plov"),
        ("лагман", "lagman"),
        ("laghman", "lagman"),
        ("манты", "manty"),
        ("manti", "manty"),
        ("самса", "samsa"),
        ("шашлык", "shashlik"),
        ("shashlik", "shashlik"),
        ("баурсаки", "baursak"),
        ("куырдак", "kuyrdak"),
        ("казы", "kazy"),
        ("кымыз", "kumys"),
        ("шубат", "kumys"),
        ("пельмени", "pelmeni"),
        ("борщ", "borscht"),
        ("хинкали", "khinkali"),
        ("хачапури", "khachapuri"),
        ("dim sum", "dimsum"),
        ("дим-самы", "dimsum"),
        ("пекинская утка", "peking_duck"),
        ("Peking duck", "peking_duck"),
        ("суши", "sushi"),
        ("роллы", "sushi"),
        ("рамен", "ramen"),
        ("пицца", "pizza"),
        ("pasta", "pasta"),
        ("бургер", "burger"),
        ("шаурма", "shawarma"),
        ("doner", "shawarma"),
        ("кофе", "coffee"),
        ("десерты", "dessert"),
    ],
)
async def test_dish_words_resolve(conn, query, slug):
    await seed(conn)
    dish = await dishes.resolve(conn, query)
    assert dish is not None and dish["slug"] == slug, query


@pytest.mark.parametrize("query", ["Кок-Тобе", "Медеу", "ресторан", "музей", "Зелёный базар", "x"])
async def test_non_dish_queries_do_not_resolve(conn, query):
    await seed(conn)
    assert await dishes.resolve(conn, query) is None


async def test_yo_and_case_are_ignored_and_dictionary_is_idempotent(conn):
    await seed(conn)
    assert dishes.normalize("  Пёс,  ПЛОВ!! ") == "пес плов"
    await conn.execute(SEED.read_text(encoding="utf-8"))  # twice: no error, no duplicates
    cur = await conn.execute("SELECT count(*) FROM dishes")
    assert (await cur.fetchone())["count"] >= 25
    dish = await dishes.resolve(conn, "бешбармак")
    assert dish["cuisines"] == ["kazakh", "central_asian"]
    assert dish["categories"][0] == "cafe_kazakh"


# ---------------------------------------------------------------- search


async def test_beshbarmak_ranks_kazakh_cuisine_first_then_related(world):
    args = tools.SearchPlacesArgs(query="бешбармак", limit=10)
    at_bazaar = recommend.Anchor(GREEN_BAZAAR[1], GREEN_BAZAAR[0], recommend.SOURCE_LODGING)
    result, pins = await tools.search_places(world.db, args, "ru", at_bazaar)
    assert result["matched"] == {"dish": "Бешбармак", "cuisines": ["kazakh", "central_asian"]}
    assert "most likely serve" in result["note"]
    assert names(result) == [
        "Дастархан",  # famous (60) and near the centre; the 99-popular one is 14 km away
        "Жайлау",
        "Қазақ асханасы далеко",
        "Чайхана Нават",  # related cuisine comes after the primary one
    ]
    assert [p["match"] for p in result["places"]] == ["cuisine"] * 3 + ["related_cuisine"]
    assert [p["name"] for p in pins] == names(result)


async def test_beshbarmak_near_the_green_bazaar_finds_kazakh_places_nearby(world):
    args = tools.SearchPlacesArgs(query="бешбармак", near="Зелёный базар", limit=5)
    result, _ = await tools.search_places(world.db, args, "ru")
    assert names(result) == ["Дастархан", "Жайлау", "Чайхана Нават"]  # best Kazakh first (Ш-68)
    assert "Қазақ асханасы далеко" not in names(result)  # ~13 km away
    assert all(p["distance_m"] < tools.NEAR_RADIUS_M for p in result["places"])
    assert result["anchor"] == "landmark"
    assert "near_not_found" not in result


@pytest.mark.parametrize("query", ["beshbarmak", "Besbarmak", "бешбармак"])
async def test_dish_in_english_and_translit_finds_the_same_places(world, query):
    args = tools.SearchPlacesArgs(query=query, near="Green bazaar zzz Зелёный базар", limit=5)
    result, _ = await tools.search_places(world.db, args, "en")
    assert result["matched"]["dish"] == "Beshbarmak"
    assert "Жайлау" in names(result)


async def test_chinese_dish_matches_chinese_cuisine_only(world):
    result, _ = await tools.search_places(world.db, tools.SearchPlacesArgs(query="dim sum"), "en")
    assert names(result) == ["Dragon Wok"]
    assert result["matched"]["cuisines"] == ["chinese", "dumpling"]


async def test_menu_text_confirms_the_dish_and_ranks_first(world):
    await world.conn.execute(
        "INSERT INTO place_menu (place_id, payload) VALUES (%s, %s::jsonb)",
        (world.ids["Dragon Wok"], json.dumps({"items": [{"name": "Бешбармак по-домашнему"}]})),
    )
    result, _ = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="beshbarmak", limit=10), "en"
    )
    assert names(result)[0] == "Dragon Wok"
    assert result["places"][0]["match"] == "menu"


async def test_a_place_named_after_the_dish_is_a_name_match(world):
    await add_place(world.conn, "Бешбармак Хаус", 76.9, 43.2, "restaurant", "active", 1)
    result, _ = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="бешбармак", limit=10), "ru"
    )
    assert result["places"][0]["name"] == "Бешбармак Хаус"
    assert result["places"][0]["match"] == "name"


async def test_category_argument_skips_dish_resolution(world):
    result, _ = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="плов", category="cafe_chinese"), "ru"
    )
    assert "matched" not in result


async def test_no_matching_place_is_an_honest_nothing_found(conn):
    await load_categories(conn)
    await conn.execute(SEED.read_text(encoding="utf-8"))
    await add_place(conn, "Тихий парк", 76.95, 43.26, "park", "active", 5)
    result, pins = await tools.search_places(
        Db(conn), tools.SearchPlacesArgs(query="бешбармак"), "ru"
    )
    assert result == {"places": [], "note": "nothing found"} and pins == []


async def test_far_closed_places_and_unknown_near(world):
    await world.conn.execute("UPDATE places SET status = 'closed' WHERE name_ru = 'Жайлау'")
    args = tools.SearchPlacesArgs(query="бешбармак", near="Несуществующая площадь Икс")
    result, _ = await tools.search_places(world.db, args, "ru")
    assert "Жайлау" not in names(result)  # closed places are never returned
    assert result["near_not_found"] is True and "near" in result["note"]


async def test_plain_name_search_keeps_working_and_supports_near(world):
    result, _ = await tools.search_places(world.db, tools.SearchPlacesArgs(query="парк"), "ru")
    assert names(result) == ["Тихий парк"] and "matched" not in result
    near = await tools.search_places(
        world.db, tools.SearchPlacesArgs(query="Қазақ", near="Зелёный базар"), "ru"
    )
    assert near[0]["places"] == []  # the only match is far away


# ---------------------------------------------------------------- guest chat and live route


async def test_guest_chat_search_understands_the_dish(chat_env, conn):
    await seed(conn)
    from app.providers.llm import FakeLLM

    llm = FakeLLM(
        steps=[
            Step(
                tool_calls=[
                    FakeToolCall("search_places", {"query": "бешбармак", "near": "Зелёный базар"})
                ]
            ),
            Step(text=["Скорее всего, там подают."]),
        ]
    )
    chat_env.app.state.llm_provider = llm
    body = {"messages": [{"role": "user", "content": "бешбармак у Зелёного базара"}]}
    response = await chat_env.client.post(
        "/v1/chat/guest", json=body, headers={"X-Install-Id": INSTALL}
    )
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    pins = [d for n, d in events if n == "map_places"][0]["places"]
    assert [p["name"] for p in pins] == ["Дастархан", "Жайлау", "Чайхана Нават"]
    tool_result = json.loads(llm.calls[1].messages[-1].content)
    assert tool_result["matched"]["dish"] == "Beshbarmak"
    assert "most likely serve" in tool_result["note"]


async def test_live_route_wish_with_a_dish_finds_stops(world):
    found = await live_route._search(world.db, "бешбармак", "ru", set())
    assert found is not None
    pins, ids = found
    # best for a tourist (Ш-68): the 99-popular place is 14 km out of town
    assert pins[0]["name"] == "Дастархан"
    assert len(ids) == live_route.MAX_PLACES_PER_WISH
