"""Known places of Kazakhstan outside the v1 area (Ш-56, SSOT §5.4 «до запуска межгорода»).

v1 plans the default region and the mountains next to it (`default_region().bbox`). When a
wish names a well-known place outside that area (Charyn, Kolsai, Turkistan…), the database has
nothing for it, and the category reading would otherwise hand the wish some park in the default
region. This small fixed list lets the search, the live route and the generator say "this is
outside the area Jol plans for now" instead of "nothing found", and lets
analytics count which regions people ask for (SSOT §16.16).

The text comes from the tourist through the model, so it is matched against fixed stems only (the
same rules as `planner.interests`): a stem matches a word that starts with it, a stem with a space
or a hyphen is looked up in the whole text. More specific entries come first (the mausoleum
before the city of Turkistan). Points are approximate and only used for a straight-line distance.
"""

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.planner.interests import SPECIFIC_FOOD, resolve
from app.regions import default_region

EARTH_RADIUS_KM = 6371.0
FOOD_SLUGS = SPECIFIC_FOOD | {"food"}

REGION_ALMATY = ("Алматинская область", "Almaty Region")
REGION_ZHETYSU = ("область Жетысу", "Zhetysu Region")
REGION_TURKISTAN = ("Туркестанская область", "Turkistan Region")


@dataclass(frozen=True)
class OutsidePlace:
    id: str  # stable slug, also the analytics property
    name_ru: str
    name_en: str
    region_ru: str
    region_en: str
    lat: float
    lon: float
    stems: Tuple[str, ...]
    not_with: Tuple[str, ...] = ()  # stems that cancel the match (Issyk lake vs Issyk-Kul)

    def name(self, locale: str) -> str:
        return self.name_en if locale == "en" else self.name_ru

    def region(self, locale: str) -> str:
        return self.region_en if locale == "en" else self.region_ru

    def distance_km(self) -> int:
        """Straight line from the region centre, rounded to 10 km (not a road distance)."""
        lat1, lon1 = map(math.radians, default_region().centre)
        lat2, lon2 = math.radians(self.lat), math.radians(self.lon)
        a = (
            math.sin((lat2 - lat1) / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
        )
        km = 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
        return int(round(km / 10.0) * 10)

    def as_json(self, locale: str) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name(locale),
            "region": self.region(locale),
            "distance_km": self.distance_km(),
        }


def _place(
    slug: str, names: Tuple[str, str], region: Tuple[str, str], point: Tuple[float, float],
    stems: Tuple[str, ...], not_with: Tuple[str, ...] = (),
) -> OutsidePlace:  # fmt: skip
    return OutsidePlace(slug, names[0], names[1], region[0], region[1], point[0], point[1],
                        stems, not_with)  # fmt: skip


PLACES: Tuple[OutsidePlace, ...] = (
    _place("charyn", ("Чарынский каньон", "Charyn Canyon"), REGION_ALMATY, (43.351, 79.080),
           ("чарын", "charyn", "sharyn", "шарын", "долина замков", "valley of castles")),
    _place("kolsai", ("Кольсайские озёра", "Kolsai Lakes"), REGION_ALMATY, (42.998, 78.326),
           ("кольсай", "колсай", "kolsai", "kolsay", "саты$", "saty$")),
    _place("kaindy", ("Озеро Каинды", "Kaindy Lake"), REGION_ALMATY, (42.985, 78.465),
           ("каинды", "kaindy", "kayindy")),
    _place("issyk_lake", ("Озеро Иссык", "Issyk Lake"), REGION_ALMATY, (43.252, 77.485),
           ("иссык", "issyk", "есик", "esik"), ("куль", "kul", "köl", "кол$")),
    _place("turgen", ("Тургеньское ущелье", "Turgen Gorge"), REGION_ALMATY, (43.300, 77.620),
           ("тургень", "turgen")),
    _place("assy", ("Плато Ассы", "Assy Plateau"), REGION_ALMATY, (43.200, 77.950),
           ("ассы$", "assy$")),
    _place("konaev", ("Конаев (Капчагай)", "Konaev (Kapchagay)"), REGION_ALMATY, (43.870, 77.070),
           ("капчагай", "капшагай", "kapchagay", "kapshagay", "конаев", "konaev", "qonaev")),
    _place("tamgaly", ("Петроглифы Тамгалы", "Tamgaly Petroglyphs"), REGION_ALMATY,
           (43.803, 75.535), ("тамгалы", "tamgaly")),
    _place("altyn_emel", ("Национальный парк Алтын-Эмель", "Altyn-Emel National Park"),
           REGION_ZHETYSU, (43.860, 78.560),
           ("алтын-эмел", "алтын эмел", "altyn-emel", "altyn emel", "поющ", "singing dune",
            "singing sand")),
    _place("yasawi", ("Мавзолей Ходжи Ахмеда Ясави", "Mausoleum of Khoja Ahmed Yasawi"),
           REGION_TURKISTAN, (43.293, 68.273),
           ("ясави", "яссави", "яссауи", "иасауи", "yasawi", "yassawi", "yasavi", "yassavi",
            "yasaui", "yesevi")),
    _place("turkistan", ("Туркестан", "Turkistan"), REGION_TURKISTAN, (43.297, 68.252),
           ("туркестан", "turkestan", "turkistan")),
    _place("otrar", ("Городище Отрар", "Otrar"), REGION_TURKISTAN, (42.852, 68.303),
           ("отрар", "otrar")),
    _place("shymkent", ("Шымкент", "Shymkent"), ("Шымкент", "Shymkent"), (42.317, 69.596),
           ("шымкент", "shymkent", "чимкент", "chimkent")),
    _place("taraz", ("Тараз", "Taraz"), ("Жамбылская область", "Zhambyl Region"), (42.900, 71.367),
           ("тараз", "taraz")),
    _place("astana", ("Астана", "Astana"), ("Астана", "Astana"), (51.128, 71.430),
           ("астан", "astana", "нур-султан", "nur-sultan")),
    _place("burabay", ("Бурабай (Боровое)", "Burabay (Borovoe)"),
           ("Акмолинская область", "Akmola Region"), (53.080, 70.300),
           ("бурабай", "burabay", "боровое", "borovoe", "borovoye")),
    _place("balkhash", ("Озеро Балхаш", "Lake Balkhash"),
           ("Карагандинская область", "Karaganda Region"), (46.500, 74.900),
           ("балхаш", "balkhash", "balqash")),
    _place("baikonur", ("Байконур", "Baikonur"), ("Кызылординская область", "Kyzylorda Region"),
           (45.965, 63.305), ("байконур", "baikonur", "baykonur")),
    _place("mangystau", ("Мангыстау (Бозжыра)", "Mangystau (Bozjyra)"),
           ("Мангистауская область", "Mangystau Region"), (43.420, 54.060),
           ("мангыстау", "мангистау", "mangystau", "mangistau", "бозжыр", "bozjyr", "bozzhyr")),
    _place("aktau", ("Актау", "Aktau"), ("Мангистауская область", "Mangystau Region"),
           (43.650, 51.170), ("актау$", "aktau$")),
)  # fmt: skip

BY_ID: Dict[str, OutsidePlace] = {p.id: p for p in PLACES}


def _tokens(text: str) -> List[str]:
    return re.findall(r"\w+", text)


def _hit(stem: str, text: str, tokens: List[str]) -> bool:
    if " " in stem or "-" in stem:
        return stem in text
    if stem.endswith("$"):
        return stem[:-1] in tokens
    return any(token.startswith(stem) for token in tokens)


def match(text: Optional[str]) -> Optional[OutsidePlace]:
    """The known place outside the v1 area that the text names, or None."""
    norm = " ".join((text or "").casefold().replace("ё", "е").split())
    if not norm:
        return None
    tokens = _tokens(norm)
    for place in PLACES:
        if any(_hit(s, norm, tokens) for s in place.stems) and not any(
            _hit(s, norm, tokens) for s in place.not_with
        ):
            return place
    return None


# Words that make "Туркестан" a venue or a street in the region, not the city: food and drink come
# from `planner.interests`, the rest is here.
VENUE_STEMS = (
    "кафе", "cafe", "café", "столов", "чайхан", "отел", "hotel", "гостиниц", "хостел", "hostel",
    "магазин", "shop", "store", "улиц", "street", "проспект", "avenue", "бульвар", "boulevard",
)  # fmt: skip


def names_a_venue(text: Optional[str]) -> bool:
    """The text is about a café, hotel, shop or street in the region named after a place
    ("ресторан Туркестан", "улица Туркестанская"), not a trip to the place itself."""
    norm = " ".join((text or "").casefold().split())
    if resolve([norm]).slugs & FOOD_SLUGS:
        return True
    tokens = _tokens(norm)
    return any(_hit(stem, norm, tokens) for stem in VENUE_STEMS)


def outside_wish(text: Optional[str]) -> Optional[OutsidePlace]:
    """`match`, unless the text is about a café or restaurant named after the place."""
    place = match(text)
    if place is None or names_a_venue(text):
        return None
    return place
