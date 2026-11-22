"""Category mapping of open datasets onto project categories (Ш-58; slugs: categories.sql).

Overture Maps Places has a taxonomy: `taxonomy.hierarchy` is a path from the broad to the
specific category (['food_and_drink', 'restaurant', 'chinese_restaurant']). The most specific
known value wins. Foursquare OS Places has `fsq_category_labels`
('Dining and Drinking > Restaurant > Chinese Restaurant'); the leaf label is mapped.
Anything not listed is skipped, as the OSM importer skips what is not tourist-relevant
(tag_mapping.classify). Shops, services, schools, clinics and the like are not places of the app.
Places of worship are not imported from these sets: thousands of small ones, and OSM keeps only
those with an encyclopedia link.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

OVERTURE = {
    # food
    "restaurant": "restaurant",
    "chinese_restaurant": "cafe_chinese",
    "dim_sum_restaurant": "cafe_chinese",
    "korean_restaurant": "cafe_korean",
    "japanese_restaurant": "cafe_japanese",
    "sushi_restaurant": "cafe_japanese",
    "ramen_restaurant": "cafe_japanese",
    "italian_restaurant": "cafe_european",
    "pizza_restaurant": "cafe_european",
    "french_restaurant": "cafe_european",
    "german_restaurant": "cafe_european",
    "spanish_restaurant": "cafe_european",
    "mediterranean_restaurant": "cafe_european",
    "european_restaurant": "cafe_european",
    "russian_restaurant": "cafe_european",
    "steakhouse": "cafe_european",
    "georgian_restaurant": "cafe_caucasian",
    "caucasian_restaurant": "cafe_caucasian",
    "armenian_restaurant": "cafe_caucasian",
    "azerbaijani_restaurant": "cafe_caucasian",
    "uzbek_restaurant": "cafe_oriental",
    "central_asian_restaurant": "cafe_oriental",
    "turkish_restaurant": "cafe_oriental",
    "middle_eastern_restaurant": "cafe_oriental",
    "asian_restaurant": "cafe_oriental",
    "indian_restaurant": "cafe_oriental",
    "arabic_restaurant": "cafe_oriental",
    "kebab_restaurant": "cafe_oriental",
    "kazakh_restaurant": "cafe_kazakh",
    "fast_food_restaurant": "cafe_fast_food",
    "burger_restaurant": "cafe_fast_food",
    "sandwich_shop": "cafe_fast_food",
    "chicken_restaurant": "cafe_fast_food",
    "food_court": "cafe_fast_food",
    "cafe": "coffee",
    "coffee_shop": "coffee",
    "tea_room": "coffee",
    "bakery": "bakery",
    "cake_shop": "bakery",
    "bar": "bar",
    "pub": "bar",
    "lounge": "bar",
    "hookah_bar": "bar",
    "cocktail_bar": "bar",
    "wine_bar": "bar",
    "beer_garden": "bar",
    "dance_club": "nightclub",
    "night_club": "nightclub",
    # lodging
    "hotel": "hotel",
    "motel": "hotel",
    "resort": "hotel",
    "lodging": "hotel",
    "hostel": "hostel",
    "guest_house": "guest_house",
    "bed_and_breakfast": "guest_house",
    "vacation_rental": "guest_house",
    # culture and sights
    "museum": "museum",
    "art_gallery": "gallery",
    "theatre_venue": "theatre",
    "performing_arts_theater": "theatre",
    "opera_house": "theatre",
    "movie_theater": "entertainment",
    "zoo": "entertainment",
    "aquarium": "entertainment",
    "planetarium": "entertainment",
    "bowling_alley": "entertainment",
    "amusement_park": "amusement",
    "water_park": "amusement",
    "theme_park": "amusement",
    "historic_site": "historic",
    "castle": "historic",
    "fort": "historic",
    "archaeological_site": "historic",
    "monument": "monument",
    "memorial": "monument",
    "landmark_and_historical_building": "landmark",
    "tourist_attraction": "landmark",
    "landmark": "landmark",
    "viewpoint": "viewpoint",
    "scenic_viewpoint": "viewpoint",
    # nature
    "park": "park",
    "national_park": "park",
    "state_park": "park",
    "garden": "garden",
    "botanical_garden": "garden",
    "nature_reserve": "mountain",
    "mountain": "mountain",
    "peak": "mountain",
    "glacier": "mountain",
    "volcano": "mountain",
    "cave": "mountain",
    "lake": "lake",
    "reservoir": "lake",
    "waterfall": "lake",
    "hot_spring": "spa",
    "sauna": "spa",
    "ski_resort": "ski",
    "ski_area": "ski",
    # shopping
    "shopping_mall": "mall",
    "department_store": "mall",
    "market": "market",
    "farmers_market": "market",
    "flea_market": "market",
    "bazaar": "market",
}

FOURSQUARE = {  # leaf label, lower case
    "restaurant": "restaurant",
    "chinese restaurant": "cafe_chinese",
    "dim sum restaurant": "cafe_chinese",
    "korean restaurant": "cafe_korean",
    "japanese restaurant": "cafe_japanese",
    "sushi restaurant": "cafe_japanese",
    "ramen restaurant": "cafe_japanese",
    "italian restaurant": "cafe_european",
    "pizzeria": "cafe_european",
    "french restaurant": "cafe_european",
    "german restaurant": "cafe_european",
    "spanish restaurant": "cafe_european",
    "mediterranean restaurant": "cafe_european",
    "eastern european restaurant": "cafe_european",
    "russian restaurant": "cafe_european",
    "steakhouse": "cafe_european",
    "georgian restaurant": "cafe_caucasian",
    "caucasian restaurant": "cafe_caucasian",
    "armenian restaurant": "cafe_caucasian",
    "azerbaijani restaurant": "cafe_caucasian",
    "central asian restaurant": "cafe_oriental",
    "uzbek restaurant": "cafe_oriental",
    "turkish restaurant": "cafe_oriental",
    "middle eastern restaurant": "cafe_oriental",
    "asian restaurant": "cafe_oriental",
    "indian restaurant": "cafe_oriental",
    "kebab restaurant": "cafe_oriental",
    "fast food restaurant": "cafe_fast_food",
    "burger joint": "cafe_fast_food",
    "sandwich spot": "cafe_fast_food",
    "food court": "cafe_fast_food",
    "café": "coffee",
    "cafe": "coffee",
    "coffee shop": "coffee",
    "tea room": "coffee",
    "bakery": "bakery",
    "dessert shop": "bakery",
    "bar": "bar",
    "pub": "bar",
    "lounge": "bar",
    "hookah bar": "bar",
    "cocktail bar": "bar",
    "wine bar": "bar",
    "beer garden": "bar",
    "nightclub": "nightclub",
    "night club": "nightclub",
    "hotel": "hotel",
    "motel": "hotel",
    "resort": "hotel",
    "hostel": "hostel",
    "bed & breakfast": "guest_house",
    "vacation rental": "guest_house",
    "museum": "museum",
    "art gallery": "gallery",
    "theater": "theatre",
    "performing arts venue": "theatre",
    "opera house": "theatre",
    "movie theater": "entertainment",
    "zoo": "entertainment",
    "aquarium": "entertainment",
    "planetarium": "entertainment",
    "bowling alley": "entertainment",
    "amusement park": "amusement",
    "water park": "amusement",
    "theme park": "amusement",
    "historic and protected site": "historic",
    "castle": "historic",
    "fort": "historic",
    "monument": "monument",
    "memorial site": "monument",
    "monument / landmark": "landmark",
    "landmarks and outdoors": "landmark",
    "scenic lookout": "viewpoint",
    "park": "park",
    "national park": "park",
    "garden": "garden",
    "botanical garden": "garden",
    "nature preserve": "mountain",
    "mountain": "mountain",
    "volcano": "mountain",
    "cave": "mountain",
    "glacier": "mountain",
    "lake": "lake",
    "reservoir": "lake",
    "waterfall": "lake",
    "hot spring": "spa",
    "sauna": "spa",
    "ski area": "ski",
    "ski resort": "ski",
    "shopping mall": "mall",
    "department store": "mall",
    "market": "market",
    "farmers market": "market",
    "flea market": "market",
    "bazaar": "market",
}


def overture_category(
    hierarchy: Optional[Sequence[str]], primary: Optional[str] = None
) -> Optional[str]:
    """Most specific known taxonomy value of an Overture place (primary first, then upwards)."""
    chain = list(reversed(hierarchy or []))
    if primary:
        chain.insert(0, primary)
    for value in chain:
        slug = OVERTURE.get(value)
        if slug:
            return slug
        if value.endswith("_museum"):
            return "museum"
    return None


def foursquare_category(labels: Optional[Iterable[str]]) -> Optional[str]:
    """First mapped leaf of the `fsq_category_labels` paths ('A > B > C' -> 'c')."""
    for label in labels or []:
        leaf = label.split(">")[-1].strip().lower()
        slug = FOURSQUARE.get(leaf)
        if slug:
            return slug
        if leaf.endswith(" museum"):
            return "museum"
    return None
