"""Request payloads of user submissions (Ш-44, SSOT §10.1). One model per submission type."""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TYPES = ("review", "menu", "photo", "transit", "price")
MAX_KZT = 1_000_000


def _line(value: Optional[str]) -> Optional[str]:
    """One line: whitespace collapsed; empty becomes None."""
    return " ".join(value.split()) or None if value is not None else None


def _required(value: str) -> str:
    line = _line(value)
    if line is None:
        raise ValueError("must not be blank")
    return line


def _clean(value: Optional[str]) -> Optional[str]:
    """Free text: trimmed, line breaks kept; empty becomes None."""
    return (value.strip() or None) if value is not None else None


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewPayload(_Payload):
    rating: int = Field(ge=1, le=5)
    text: Optional[str] = Field(None, max_length=2000)

    _text = field_validator("text")(lambda cls, v: _clean(v))


class MenuItem(_Payload):
    name: str = Field(min_length=1, max_length=120)
    price_kzt: Optional[int] = Field(None, ge=0, le=MAX_KZT)
    description: Optional[str] = Field(None, max_length=300)

    _name = field_validator("name")(lambda cls, v: _required(v))
    _description = field_validator("description")(lambda cls, v: _line(v))


class MenuPayload(_Payload):
    """A menu as items with prices and/or a photo of it (`upload_id`)."""

    items: List[MenuItem] = Field(default_factory=list, max_length=100)
    upload_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _something(self) -> "MenuPayload":
        if not self.items and self.upload_id is None:
            raise ValueError("a menu needs items or a photo")
        return self


class PhotoPayload(_Payload):
    upload_id: UUID
    caption: Optional[str] = Field(None, max_length=200)

    _caption = field_validator("caption")(lambda cls, v: _line(v))


class TransitPayload(_Payload):
    """Free-form structured transit data: which route, where it stops, how often, the fare."""

    route_ref: str = Field(min_length=1, max_length=40)
    stop: Optional[str] = Field(None, max_length=120)
    direction: Optional[str] = Field(None, max_length=120)
    interval_min: Optional[int] = Field(None, ge=1, le=240)
    price_kzt: Optional[int] = Field(None, ge=0, le=MAX_KZT)
    note: Optional[str] = Field(None, max_length=300)

    _route = field_validator("route_ref")(lambda cls, v: _required(v))
    _text = field_validator("stop", "direction", "note")(lambda cls, v: _line(v))


class PricePayload(_Payload):
    """Entry price of a place; `audience` tells which ticket it is."""

    price_kzt: int = Field(ge=0, le=MAX_KZT)
    audience: Literal["adult", "child", "student", "senior", "foreigner", "resident"] = "adult"
    note: Optional[str] = Field(None, max_length=200)

    _note = field_validator("note")(lambda cls, v: _line(v))


MODELS = {
    "review": ReviewPayload,
    "menu": MenuPayload,
    "photo": PhotoPayload,
    "transit": TransitPayload,
    "price": PricePayload,
}


class SubmissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["review", "menu", "photo", "transit", "price"]
    place_id: Optional[UUID] = None  # required for every type except transit
    payload: Dict[str, Any]


class UploadIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(gt=0)
