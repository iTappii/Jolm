"""Localized events shared by the map and place cards."""

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class EventVenue(BaseModel):
    id: UUID
    name: str


class EventItem(BaseModel):
    id: UUID
    title: str
    title_lang: Optional[str]
    description: Optional[str]
    starts_at: datetime
    ends_at: Optional[datetime]
    price_kzt: Optional[int]
    organizer: Optional[str]
    category: Optional[str]
    lat: float
    lon: float
    place: Optional[EventVenue]
    is_ad: bool
    ad_label: Optional[Literal["Реклама", "Ad"]]


class EventList(BaseModel):
    items: List[EventItem]
