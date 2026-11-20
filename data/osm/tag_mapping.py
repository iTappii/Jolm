"""Pure functions: OSM tags -> Jol place fields. No I/O, no database.

Category slugs come from data/seed/categories.sql. The mapping is deliberately conservative:
unnamed objects and objects that are not tourist-relevant are skipped (classify() -> None).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

# Tag keys the importer cares about (used to pre-filter the planet file at C level).
INTERESTING_KEYS = (
    "tourism",
    "amenity",
    "leisure",
    "natural",
    "historic",
    "shop",
    "landuse",
)

# slug -> (kind, setting, is_public)
# kind: landmark|venue|nature|accommodation|event_venue; setting: indoor|outdoor|mixed
# is_public: state/public places and sights (SSOT §12 — never advertising)
CATEGORY_DEFAULTS: Dict[str, tuple] = {
    "landmark": ("landmark", "outdoor", True),
    "monument": ("landmark", "outdoor", True),
    "historic": ("landmark", "outdoor", True),
    "religious": ("landmark", "mixed", True),
    "museum": ("venue", "indoor", True),
    "gallery": ("venue", "indoor", False),
    "theatre": ("event_venue", "indoor", True),
    "entertainment": ("venue", "indoor", False),
    "amusement": ("venue", "outdoor", False),
    "spa": ("venue", "indoor", False),
    "park": ("nature", "outdoor", True),
    "garden": ("nature", "outdoor", True),
    "mountain": ("nature", "outdoor", True),
    "viewpoint": ("landmark", "outdoor", True),
    "lake": ("nature", "outdoor", True),
    "ski": ("nature", "outdoor", False),
    "market": ("venue", "mixed", False),
    "mall": ("venue", "indoor", False),
    "restaurant": ("venue", "indoor", False),
    "cafe_kazakh": ("venue", "indoor", False),
    "cafe_oriental": ("venue", "indoor", False),
    "cafe_chinese": ("venue", "indoor", False),
    "cafe_korean": ("venue", "indoor", False),
    "cafe_japanese": ("venue", "indoor", False),
    "cafe_european": ("venue", "indoor", False),
    "cafe_caucasian": ("venue", "indoor", False),
    "cafe_fast_food": ("venue", "indoor", False),
    "coffee": ("venue", "indoor", False),
    "bakery": ("venue", "indoor", False),
    "bar": ("venue", "indoor", False),
    "nightclub": ("venue", "indoor", False),
    "hotel": ("accommodation", "indoor", False),
    "hostel": ("accommodation", "indoor", False),
    "guest_house": ("accommodation", "indoor", False),
}

# cuisine value -> category slug (first match in the ';'-separated list wins)
CUISINE_CATEGORY = {
    "kazakh": "cafe_kazakh",
    "kazakhstani": "cafe_kazakh",
    "national": "cafe_kazakh",
    "uzbek": "cafe_oriental",
    "central_asian": "cafe_oriental",
    "uyghur": "cafe_oriental",
    "tajik": "cafe_oriental",
    "kyrgyz": "cafe_oriental",
    "turkish": "cafe_oriental",
    "arab": "cafe_oriental",
    "lebanese": "cafe_oriental",
    "middle_eastern": "cafe_oriental",
    "persian": "cafe_oriental",
    "afghan": "cafe_oriental",
    "indian": "cafe_oriental",
    "asian": "cafe_oriental",
    "kebab": "cafe_oriental",
    "chinese": "cafe_chinese",
    "dumpling": "cafe_chinese",
    "korean": "cafe_korean",
    "japanese": "cafe_japanese",
    "sushi": "cafe_japanese",
    "ramen": "cafe_japanese",
    "european": "cafe_european",
    "italian": "cafe_european",
    "pizza": "cafe_european",
    "french": "cafe_european",
    "german": "cafe_european",
    "spanish": "cafe_european",
    "mediterranean": "cafe_european",
    "steak_house": "cafe_european",
    "russian": "cafe_european",
    "georgian": "cafe_caucasian",
    "caucasian": "cafe_caucasian",
    "armenian": "cafe_caucasian",
    "azerbaijani": "cafe_caucasian",
    "burger": "cafe_fast_food",
    "fast_food": "cafe_fast_food",
    "sandwich": "cafe_fast_food",
    "chicken": "cafe_fast_food",
    "coffee_shop": "coffee",
    "coffee": "coffee",
    "tea": "coffee",
    "cake": "bakery",
    "bakery": "bakery",
}

TOURISM = {
    "attraction": "landmark",
    "museum": "museum",
    "gallery": "gallery",
    "viewpoint": "viewpoint",
    "zoo": "entertainment",
    "aquarium": "entertainment",
    "theme_park": "amusement",
    "hotel": "hotel",
    "motel": "hotel",
    "hostel": "hostel",
    "guest_house": "guest_house",
    "apartment": "guest_house",
    "chalet": "guest_house",
}

HISTORIC = {
    "monument": "monument",
    "memorial": "monument",
    "castle": "historic",
    "fort": "historic",
    "ruins": "historic",
    "archaeological_site": "historic",
    "building": "historic",
    "manor": "historic",
    "tomb": "historic",
    "wayside_cross": None,  # noise
}

# Plain memorials/monuments are numerous; keep only ones with an encyclopedic link
NEEDS_WIKI = {"monument", "memorial", "building", "tomb"}

AMENITY = {
    "restaurant": "restaurant",  # refined by cuisine
    "cafe": "coffee",  # refined by cuisine
    "fast_food": "cafe_fast_food",
    "food_court": "cafe_fast_food",
    "bar": "bar",
    "pub": "bar",
    "biergarten": "bar",
    "nightclub": "nightclub",
    "theatre": "theatre",
    "arts_centre": "gallery",
    "cinema": "entertainment",
    "planetarium": "entertainment",
    "marketplace": "market",
    "public_bath": "spa",
    "place_of_worship": "religious",  # only with a wiki link, see classify()
}

LEISURE = {
    "park": "park",
    "garden": "garden",
    "nature_reserve": "mountain",
    "water_park": "amusement",
    "bowling_alley": "entertainment",
    "escape_game": "entertainment",
    "sauna": "spa",
}

NATURAL = {
    "peak": "mountain",
    "waterfall": "lake",
    "glacier": "mountain",
    "cave_entrance": "mountain",
    "hot_spring": "spa",
}

SHOP = {
    "mall": "mall",
    "department_store": "mall",
    "bakery": "bakery",
    "pastry": "bakery",
    "confectionery": "bakery",
}

# Mountain-ish categories where a high elevation means "this is a trip into the mountains"
MOUNTAIN_CATEGORIES = {"mountain", "lake", "ski", "viewpoint"}
MOUNTAIN_ELEVATION_M = 1200

_KK_LETTERS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
_CYR = re.compile(r"[Ѐ-ӿ]")
_LAT = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class PlaceSpec:
    category: str
    kind: str
    setting: str
    is_public: bool
    is_mountain: bool
    elevation_m: Optional[int]
    name_ru: Optional[str]
    name_en: Optional[str]
    name_kk: Optional[str]
    address_ru: Optional[str]
    address_en: Optional[str]
    website: Optional[str]


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _has_wiki(tags: Mapping[str, str]) -> bool:
    return bool(tags.get("wikidata") or tags.get("wikipedia"))


def parse_elevation(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    m = re.match(r"^\s*(-?\d+(?:[.,]\d+)?)\s*(?:m|м)?\s*$", value)
    if not m:
        return None
    try:
        return int(round(float(m.group(1).replace(",", "."))))
    except ValueError:
        return None


def pick_names(tags: Mapping[str, str]) -> tuple:
    """Return (name_ru, name_en, name_kk). Falls back to the plain `name` by script."""
    name = _clean(tags.get("name"))
    ru = _clean(tags.get("name:ru"))
    en = _clean(tags.get("name:en")) or _clean(tags.get("int_name"))
    kk = _clean(tags.get("name:kk"))
    if name:
        has_cyr = bool(_CYR.search(name))
        has_kk = any(ch in _KK_LETTERS for ch in name)
        if ru is None and has_cyr and not has_kk and name != kk:
            ru = name
        if en is None and _LAT.search(name) and not has_cyr:
            en = name
        if kk is None and has_kk:
            kk = name
    return ru, en, kk


def pick_address(tags: Mapping[str, str]) -> tuple:
    street = _clean(tags.get("addr:street"))
    if not street:
        return None, None
    number = _clean(tags.get("addr:housenumber"))
    text = f"{street}, {number}" if number else street
    if _CYR.search(text):
        return text, None
    return None, text


def category_for_food(amenity_value: str, tags: Mapping[str, str]) -> str:
    base = AMENITY[amenity_value]
    if amenity_value not in ("restaurant", "cafe", "fast_food"):
        return base
    for raw in (tags.get("cuisine") or "").lower().split(";"):
        slug = CUISINE_CATEGORY.get(raw.strip().replace(" ", "_"))
        if slug:
            # fast_food stays fast food unless it is a plain coffee/bakery tag
            if amenity_value == "fast_food" and slug not in ("coffee", "bakery"):
                return "cafe_fast_food"
            return slug
    return base


def category_slug(tags: Mapping[str, str]) -> Optional[str]:
    """Pick the single best category for an OSM object, or None if not relevant."""
    tourism = tags.get("tourism")
    if tourism in TOURISM:
        return TOURISM[tourism]
    amenity = tags.get("amenity")
    if amenity in AMENITY:
        if amenity == "place_of_worship" and not _has_wiki(tags):
            return None
        return category_for_food(amenity, tags)
    historic = tags.get("historic")
    if historic in HISTORIC and HISTORIC[historic]:
        if historic in NEEDS_WIKI and not _has_wiki(tags):
            return None
        return HISTORIC[historic]
    leisure = tags.get("leisure")
    if leisure in LEISURE:
        return LEISURE[leisure]
    natural = tags.get("natural")
    if natural in NATURAL:
        return NATURAL[natural]
    if natural == "water" and tags.get("water") in ("lake", "reservoir"):
        return "lake"
    if tags.get("landuse") == "winter_sports":
        return "ski"
    shop = tags.get("shop")
    if shop in SHOP:
        return SHOP[shop]
    return None


def classify(tags: Mapping[str, str]) -> Optional[PlaceSpec]:
    """Map OSM tags to place fields; None when the object is unnamed or not a tourist place."""
    ru, en, kk = pick_names(tags)
    if not (ru or en or kk):
        return None
    slug = category_slug(tags)
    if slug is None:
        return None
    kind, setting, is_public = CATEGORY_DEFAULTS[slug]
    ele = parse_elevation(tags.get("ele"))
    is_mountain = (
        tags.get("natural") in ("peak", "glacier") or tags.get("landuse") == "winter_sports"
    )
    if not is_mountain and slug in MOUNTAIN_CATEGORIES and ele is not None:
        is_mountain = ele >= MOUNTAIN_ELEVATION_M
    addr_ru, addr_en = pick_address(tags)
    website = _clean(tags.get("website")) or _clean(tags.get("contact:website"))
    return PlaceSpec(
        category=slug,
        kind=kind,
        setting=setting,
        is_public=is_public,
        is_mountain=is_mountain,
        elevation_m=ele,
        name_ru=ru,
        name_en=en,
        name_kk=kk,
        address_ru=addr_ru,
        address_en=addr_en,
        website=website,
    )
