"""Push notifications (Ш-40): `PushProvider` interface, APNs adapter, logging stub.

`make_push(settings)`: `push_provider = "apns"` sends through APNs (token authentication; needs
the Apple Developer team id, a push key id and its .p8 key: CREDENTIAL GAP, not provisioned);
anything else is the logging stub that sends nothing (dev, tests).
"""

from app.config import Settings
from app.push.apns import ApnsProvider
from app.push.base import LogPushProvider, PushError, PushMessage, PushOutcome, PushProvider

__all__ = [
    "ApnsProvider",
    "LogPushProvider",
    "PushError",
    "PushMessage",
    "PushOutcome",
    "PushProvider",
    "make_push",
]


def make_push(settings: Settings) -> PushProvider:
    if settings.push_provider != "apns":
        return LogPushProvider()
    key = settings.apns_private_key.get_secret_value()
    if not (settings.apns_team_id and settings.apns_key_id and key):
        raise PushError(
            "push_provider=apns needs APNS_TEAM_ID, APNS_KEY_ID and APNS_PRIVATE_KEY "
            "(credential gap: Apple Developer account not provisioned)"
        )
    return ApnsProvider(
        settings.apns_team_id,
        settings.apns_key_id,
        key,
        settings.apns_topic or settings.apple_client_id,
        sandbox=settings.apns_sandbox,
    )
