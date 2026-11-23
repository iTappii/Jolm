from typing import List, Literal, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.routing.base import Point

# Ш-61: plane, train and tour only appear in the legs of a trip across the country (intercity)
Mode = Literal["walk", "scooter", "bus", "metro", "taxi", "car", "plane", "train", "tour"]
Group = Literal["walk", "transit", "taxi", "scooter", "car", "intercity"]


def group_of(mode: str) -> str:
    """The client's tab for a mode: bus and metro are both "transit", plane/train/tour are
    "intercity", the rest are their own."""
    if mode in ("bus", "metro"):
        return "transit"
    return "intercity" if mode in ("plane", "train", "tour") else mode


class RoutePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90, strict=True)  # inside the region: checked by the API
    lon: float = Field(ge=-180, le=180, strict=True)

    def as_point(self) -> Point:
        return self.lat, self.lon


class DirectionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: RoutePoint = Field(alias="from")
    to_place_id: Optional[UUID] = None
    to: Optional[RoutePoint] = None
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
    # Ш-22a: several path variants per transport group (the client shows them as alternatives).
    group: Optional[Group] = None  # filled from `mode` when not given
    variant: int = 0  # 0 = the optimal variant of its group, then 1, 2 (see service._rank)
    arrive_at: Optional[str] = None  # ISO datetime with offset, region time zone
    # OPEN(SSOT §16.14): no traffic/crowding source yet; the API always sends null.
    congestion: Optional[float] = None

    @model_validator(mode="after")
    def _default_group(self):
        if self.group is None:
            self.group = group_of(self.mode)  # type: ignore[assignment]
        return self
