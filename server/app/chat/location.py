"""The tourist's position sent by the app with a chat request (Ш-68).

Used for this one request only, to measure "near me": never stored, never logged, and never sent
to the model as coordinates (the model gets distances only, see places/recommend.py). `repr` hides
the numbers so a log line or an error report cannot leak them.
"""

from typing import Tuple

from pydantic import BaseModel, Field


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)

    def __repr__(self) -> str:
        return "Location(...)"

    __str__ = __repr__

    def point(self) -> Tuple[float, float]:
        return (self.lat, self.lon)
