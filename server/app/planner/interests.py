"""Free text (interests, must-haves; RU and EN) -> place categories.

The text comes from the tourist through the model, so it is matched against a fixed keyword
table: nothing from it reaches SQL except as a bound parameter. A stem matches a word that
starts with it; a stem ending in `$` must equal the word; a stem with a space is looked up in
the whole text. Slugs are category slugs from `data/seed/categories.sql`; a group slug (for
example `food`, `nature`) stands for all categories under it.
"""

import re
from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Tuple

OUTDOOR = "outdoor"  # pseudo slug: prefer places whose setting is outdoor
EVENTS = "events"  # pseudo slug: the person wants events (event bonus counts double)

SPECIFIC_FOOD = frozenset(
    ["restaurant", "coffee", "bakery", "bar", "nightclub"]
    + ["cafe_chinese", "cafe_korean", "cafe_japanese", "cafe_kazakh", "cafe_oriental"]
    + ["cafe_european", "cafe_caucasian", "cafe_fast_food"]
)

# (stems, slugs)
KEYWORDS: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = [
    # cuisines
    (("китай", "chinese", "china"), ("cafe_chinese",)),
    (("корей", "korean"), ("cafe_korean",)),
    (("япон", "japan", "суши", "sushi", "рамен", "ramen"), ("cafe_japanese",)),
    (("казах", "kazakh", "бешбармак", "beshbarmak", "национальн"), ("cafe_kazakh",)),
    (("восточ", "oriental", "central asia", "средне", "uyghur", "уйгур"), ("cafe_oriental",)),
    (
        ("узбек", "uzbek", "плов", "plov", "pilaf", "лагман", "lagman", "самса", "samsa"),
        ("cafe_oriental", "cafe_kazakh"),
    ),
    (
        (
            "европ",
            "european",
            "итальян",
            "italian",
            "pizza",
            "пицц",
            "паста$",
            "pasta$",
            "француз",
            "french",
        ),
        ("cafe_european",),
    ),
    (
        ("кавказ", "caucas", "грузин", "georgia", "хинкал", "khinkali", "шашлык", "shashlik"),
        ("cafe_caucasian",),
    ),
    (("фастфуд", "fast food", "burger", "бургер"), ("cafe_fast_food",)),
    (("кофе", "coffee", "кофейн"), ("coffee",)),
    (("пекарн", "bakery", "выпечк", "pastry", "кондитер", "dessert", "десерт"), ("bakery",)),
    (("паб$", "pub$", "бар$", "bar$", "beer", "пиво", "cocktail", "коктейл"), ("bar",)),
    (("nightlife", "ночн", "club$", "клуб"), ("nightclub", "bar")),
    (("ресторан", "restaurant"), ("restaurant",)),
    (("food$", "еда$", "кухн", "cuisine", "поесть", "eat$"), ("food",)),
    # culture
    (("музе", "museum"), ("museum",)),
    (("выставк", "exhibit", "галере", "galler", "искусств", "art$"), ("gallery", "museum")),
    (("театр", "theat", "концерт", "concert", "опер$", "opera", "балет", "ballet"), ("theatre",)),
    (("истори", "histor", "heritage", "наследи"), ("historic", "monument", "museum", "landmark")),
    (("мечет", "mosque", "храм", "church", "собор", "cathedral", "religi"), ("religious",)),
    (("достопримеч", "sightsee", "landmark", "sights$", "sight$"), ("sights",)),
    (
        (
            "развлеч",
            "entertain",
            "family",
            "семейн",
            "дети$",
            "детей",
            "kids",
            "children",
            "аттракцион",
            "amusement",
            "attraction",
            "bowling",
        ),
        ("entertainment", "amusement"),
    ),
    (("баня$", "бани$", "sauna", "сауна", "hammam", "хамам", "wellness", "спа$", "spa$"), ("spa",)),
    (
        (
            "рынок",
            "рынк",
            "базар",
            "bazaar",
            "market",
            "shop",
            "магазин",
            "шопинг",
            "mall",
            "торгов",
            "сувенир",
            "souvenir",
        ),
        ("market", "mall"),
    ),
    # nature
    (
        ("природ", "nature", "outdoor", "open air", "под открытым", "прогулк", "walk", "на улице"),
        (OUTDOOR, "nature"),
    ),
    (
        ("горы$", "горн", "mountain", "hik", "поход", "trek", "трек", "trail", "тропа", "тропы"),
        (OUTDOOR, "mountain", "viewpoint", "lake"),
    ),
    (("парк$", "парки$", "park$", "parks$", "garden", "сад$", "ботан"), ("park", "garden")),
    (("озер", "озёр", "lake", "waterfall", "водопад"), ("lake",)),
    (("вид$", "смотров", "panoram", "панорам", "view$", "views$"), ("viewpoint",)),
    (("лыж", "ski$", "skiing", "сноуборд", "snowboard"), ("ski",)),
    # events
    (("event", "ивент", "мероприят", "фестивал", "festival"), (EVENTS,)),
]


@dataclass(frozen=True)
class Resolved:
    slugs: FrozenSet[str]  # category / group slugs, without the pseudo slugs
    outdoor: bool
    events: bool

    @property
    def empty(self) -> bool:
        return not self.slugs


def _tokens(text: str) -> List[str]:
    return re.findall(r"[\w]+", text.casefold())


def _matches(stem: str, text: str, tokens: List[str]) -> bool:
    if " " in stem:
        return stem in text
    if stem.endswith("$"):
        return stem[:-1] in tokens
    return any(token.startswith(stem) for token in tokens)


def resolve(texts: Iterable[str]) -> Resolved:
    """Categories and flags that the given free-text items point to."""
    slugs = set()
    for raw in texts:
        text = " ".join(raw.casefold().split())
        tokens = _tokens(text)
        for stems, targets in KEYWORDS:
            if any(_matches(stem, text, tokens) for stem in stems):
                slugs.update(targets)
    outdoor, events = OUTDOOR in slugs, EVENTS in slugs
    slugs -= {OUTDOOR, EVENTS}
    if "food" in slugs and slugs & SPECIFIC_FOOD:  # "восточная кухня" is not "any food"
        slugs.discard("food")
    return Resolved(
        slugs=frozenset(slugs),
        outdoor=outdoor,
        events=events,
    )
