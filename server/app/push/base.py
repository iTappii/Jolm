"""Push interface. A provider sends ONE message to ONE device token."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Protocol

log = logging.getLogger("app.push")


class PushError(Exception):
    """Transient or configuration failure: the `push.send` job is retried."""


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)  # custom keys next to `aps`


@dataclass(frozen=True)
class PushOutcome:
    ok: bool
    invalid_token: bool = False  # the device no longer accepts this token: forget it
    detail: str = ""


class PushProvider(Protocol):
    async def send(self, token: str, message: PushMessage) -> PushOutcome: ...


class LogPushProvider:
    """Sends nothing; logs that a push would have gone out (no token, no text: no personal data)."""

    async def send(self, token: str, message: PushMessage) -> PushOutcome:
        log.info("push not sent (log provider)", extra={"kind": message.data.get("type")})
        return PushOutcome(ok=True, detail="log provider")
