"""APNs adapter, token-based authentication (HTTP/2, ES256 JWT).

NOT verified against Apple: there is no paid Apple Developer account, so no team id, key id or
.p8 key exists yet (credential gap). Written to Apple's documented format and tested only with a
mock transport. Tokens: the JWT is reused for 40 minutes (Apple wants 20..60 minutes).
"""

import json
import logging
import time
from typing import Any, Callable, Optional

import httpx
import jwt

from app.push.base import PushError, PushMessage, PushOutcome

log = logging.getLogger("app.push")

PRODUCTION_HOST = "https://api.push.apple.com"
SANDBOX_HOST = "https://api.sandbox.push.apple.com"
JWT_TTL_SEC = 40 * 60
TIMEOUT_SEC = 10.0
# Apple reasons for a token that will never work again
DEAD_TOKEN_REASONS = {"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"}


class ApnsProvider:
    def __init__(
        self,
        team_id: str,
        key_id: str,
        private_key_pem: str,
        topic: str,
        sandbox: bool = True,
        client: Optional[httpx.AsyncClient] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.team_id, self.key_id, self.topic = team_id, key_id, topic
        self._key = private_key_pem.replace("\\n", "\n")
        self.host = SANDBOX_HOST if sandbox else PRODUCTION_HOST
        self._client = client
        self._clock = clock
        self._jwt: Optional[str] = None
        self._jwt_at = 0.0

    def _client_or_new(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(http2=True, timeout=TIMEOUT_SEC)
        return self._client

    def _token(self) -> str:
        now = self._clock()
        if self._jwt is None or now - self._jwt_at > JWT_TTL_SEC:
            self._jwt = jwt.encode(
                {"iss": self.team_id, "iat": int(now)},
                self._key,
                algorithm="ES256",
                headers={"kid": self.key_id},
            )
            self._jwt_at = now
        return self._jwt

    async def send(self, token: str, message: PushMessage) -> PushOutcome:
        payload: dict = {
            "aps": {"alert": {"title": message.title, "body": message.body}, "sound": "default"}
        }
        payload.update(message.data)
        headers = {
            "authorization": "bearer " + self._token(),
            "apns-topic": self.topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        try:
            response = await self._client_or_new().post(
                "%s/3/device/%s" % (self.host, token), headers=headers, content=json.dumps(payload)
            )
        except httpx.HTTPError as exc:
            raise PushError("apns request failed: %s" % type(exc).__name__) from None
        if response.status_code == 200:
            return PushOutcome(ok=True)
        reason = _reason(response)
        if response.status_code == 410 or reason in DEAD_TOKEN_REASONS:
            return PushOutcome(ok=False, invalid_token=True, detail=reason)
        if reason == "ExpiredProviderToken":
            self._jwt = None  # sign a new one on the retry
        raise PushError("apns rejected the push: %s %s" % (response.status_code, reason))

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()


def _reason(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
        return str(body.get("reason", ""))
    except (ValueError, AttributeError):
        return ""
