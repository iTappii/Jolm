"""Plain data the planner works with."""

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass(frozen=True)
class Place:
    id: UUID
    name_ru: Optional[str]
    name_en: Optional[str]
    category: Optional[str]  # category slug
    parent: Optional[str]  # slug of its group (sights, nature, food, ...), None for a group itself
    kind: str
    setting: Optional[str]  # indoor | outdoor | mixed
    outdoor: bool  # the category suffers from bad weather
    lat: float
    lon: float
    popularity: int
    is_public: bool
    is_mountain: bool
    typical_visit_min: Optional[int]
    entry_price_kzt: Optional[int]
    avg_check_kzt: Optional[int]

    @property
    def is_food(self) -> bool:
        return "food" in (self.category, self.parent)

    @property
    def name(self) -> str:
        return self.name_ru or self.name_en or ""


def place_from_row(row: Dict[str, Any]) -> Place:
    return Place(
        id=row["id"],
        name_ru=row["name_ru"],
        name_en=row["name_en"],
        category=row["category"],
        parent=row["parent"],
        kind=row["kind"],
        setting=row["setting"],
        outdoor=bool(row["outdoor"]),
        lat=row["lat"],
        lon=row["lon"],
        popularity=row["popularity"] or 0,
        is_public=row["is_public"],
        is_mountain=row["is_mountain"],
        typical_visit_min=row["typical_visit_min"],
        entry_price_kzt=row["entry_price_kzt"],
        avg_check_kzt=row["avg_check_kzt"],
    )
