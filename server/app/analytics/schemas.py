"""Analytics request schemas (Ш-50)."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

MAX_BATCH = 50


class ClientEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID  # made by the client once per event; a retry of the same batch is deduplicated
    name: str = Field(min_length=1, max_length=40)
    ts: Optional[AwareDatetime] = None  # the device clock when it happened
    place_id: Optional[UUID] = None
    # raw on purpose: a bad or unknown property is dropped, not a reason to lose the event
    props: Dict[str, Any] = Field(default_factory=dict, max_length=20)


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sent_at: Optional[AwareDatetime] = None  # the device clock when the batch was sent
    events: List[ClientEvent] = Field(min_length=1, max_length=MAX_BATCH)
