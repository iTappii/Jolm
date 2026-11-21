from typing import List, Literal, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.routing.base import Point

Mode = Literal["walk", "scooter", "bus", "metro", "taxi", "car"]


class AlmatyPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=43.0, le=43.45, strict=True)
    lon: float = Field(ge=76.70, le=77.20, strict=True)

    def as_point(self) -> Point:
        return self.lat, self.lon


class DirectionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: AlmatyPoint = Field(alias="from")
    to_place_id: Optional[UUID] = None
    to: Optional[AlmatyPoint] = None
    depart_at: Optional[AwareDatetime] = None

    @field_validator("depart_at", mode="before")
    @classmethod
    def validate_departure_format(cls, value):
        if value is not None and (not isinstance(value, str) or "T" not in value):
            raise ValueError("depart_at must be an ISO 8601 timestamp with an offset")
        return value

    @model_validator(mode="after")
    def validate_destination(self):
        if (self.to_place_id is None) == (self.to is None):
            raise ValueError("Provide exactly one of to_place_id and to")
        return self


class DirectionStep(BaseModel):
    type: Literal["walk", "ride", "maneuver"]
    duration_s: float
    distance_m: float
    geometry: str
    instruction: Optional[str] = None
    from_name: Optional[str] = None
    to_name: Optional[str] = None
    from_name_en: Optional[str] = None
    to_name_en: Optional[str] = None
    route_id: Optional[str] = None
    route_ref: Optional[str] = None
    kind: Optional[str] = None
    n_stops: Optional[int] = None
    wait_s: Optional[float] = None


class DirectionOption(BaseModel):
    mode: Mode
    duration_s: float
    duration_s_min: Optional[float] = None
    duration_s_max: Optional[float] = None
    distance_m: float
    cost_kzt_min: int
    cost_kzt_max: int
    geometry: str
    steps: Optional[List[DirectionStep]] = None
    approximate: bool
    recommended: bool = False
