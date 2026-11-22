"""A region: where Jol plans trips (SSOT §1). Plain data; no database access here."""

from dataclasses import dataclass
from typing import Tuple
from zoneinfo import ZoneInfo

Point = Tuple[float, float]  # (lat, lon)


@dataclass(frozen=True)
class Region:
    id: str
    name_ru: str
    name_en: str
    timezone: str
    currency: str
    languages: Tuple[str, ...]
    centre: Point  # (lat, lon)
    zoom: float  # default map camera zoom
    bbox: Tuple[float, float, float, float]  # (west, south, east, north) of the boundary
    is_default: bool = False

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)  # ZoneInfo caches instances

    def name(self, locale: str) -> str:
        return self.name_ru if locale == "ru" else self.name_en

    def contains(self, lat: float, lon: float) -> bool:
        """Inside the bounding box of the boundary (the boundary is a rectangle for now)."""
        west, south, east, north = self.bbox
        return south <= lat <= north and west <= lon <= east

    def to_json(self) -> dict:
        """The public shape of `GET /v1/regions`."""
        return {
            "id": self.id,
            "name": {"ru": self.name_ru, "en": self.name_en},
            "timezone": self.timezone,
            "currency": self.currency,
            "languages": list(self.languages),
            "centre": {"lat": self.centre[0], "lon": self.centre[1]},
            "camera": {"zoom": self.zoom},
            "bbox": list(self.bbox),
            "is_default": self.is_default,
        }
