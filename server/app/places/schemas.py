"""Response schemas for the places API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class PlaceSummary(BaseModel):
    """Lightweight item for map pins and lists."""

    id: UUID
    name: str
    name_lang: Optional[str] = None  # language the name actually came from: ru | en | kk
    category: Optional[str] = None
    kind: str
    lat: float
    lon: float
    is_public: bool
    is_partner: bool
    popularity: int


class PlacesList(BaseModel):
    items: List[PlaceSummary]


class Names(BaseModel):
    ru: Optional[str] = None
    en: Optional[str] = None
    kk: Optional[str] = None


class CategoryRef(BaseModel):
    slug: str
    name: str


class Interval(BaseModel):
    opens: str  # "HH:MM"
    closes: str  # "HH:MM"; closes <= opens means past midnight


class DayHours(BaseModel):
    weekday: int  # 0 = Monday .. 6 = Sunday
    intervals: List[Interval]


class Photo(BaseModel):
    id: UUID
    storage_key: str
    url: Optional[str] = None  # `MEDIA_BASE_URL/<storage_key>`; null while MEDIA_BASE_URL is unset
    source: str


class Menu(BaseModel):
    payload: Dict[str, Any]
    source: str
    updated_at: datetime


class Prices(BaseModel):
    entry_price_kzt: Optional[int] = None
    avg_check_kzt: Optional[int] = None
    price_per_night_kzt: Optional[int] = None


class PlaceDetail(BaseModel):
    id: UUID
    name: str
    name_lang: Optional[str] = None
    names: Names
    description: Optional[str] = None
    category: Optional[CategoryRef] = None
    kind: str
    setting: Optional[str] = None
    lat: float
    lon: float
    address: Optional[str] = None
    website: Optional[str] = None
    prices: Prices
    typical_visit_min: Optional[int] = None
    is_public: bool
    is_partner: bool
    is_mountain: bool
    elevation_m: Optional[int] = None
    popularity: int
    photos: List[Photo]
    hours: List[DayHours]
    open_now: Optional[bool] = None  # null when no hours are known
    menu: Optional[Menu] = None
    crowd: Optional[Any] = None  # filled in Ф15
    data_updated_at: datetime


class Category(BaseModel):
    slug: str
    parent: Optional[str] = None
    name: str
    outdoor: bool
    sort_order: int


class CategoriesList(BaseModel):
    items: List[Category]


class CuratedRouteSummary(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    places_count: int


class CuratedRoutesList(BaseModel):
    items: List[CuratedRouteSummary]


class CuratedRouteItem(PlaceSummary):
    ord: int


class CuratedRouteDetail(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    items: List[CuratedRouteItem]
