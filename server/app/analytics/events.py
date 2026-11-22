"""Event whitelist (Ш-50): which events exist, who may send them, which properties they carry.

Client events are the ones the server cannot see (install, launch, directions started). The
others are written by the server itself and a client that sends them is told they are rejected:
a person could otherwise inflate the funnel with fake route_created events.
"""

from typing import Any, Callable, Dict, Optional

from app.planner.outside import BY_ID

CLIENT_EVENTS = ("app_install", "app_launch", "directions_start")
SERVER_EVENTS = (
    "sign_in", "route_created", "place_shown", "trip_downloaded", "wish_outside_area",
)  # fmt: skip

MAX_PROP_STR = 40
OUTSIDE_IDS = tuple(BY_ID)
MODES = ("walk", "scooter", "bus", "metro", "taxi", "car")
PROVIDERS = ("email", "phone", "apple")


def _short_str(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_PROP_STR


def _one_of(*allowed: str) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, str) and value in allowed


def _small_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10_000


def _flag(value: Any) -> bool:
    return isinstance(value, bool)


# event -> {property key: validator}. A key not listed here is dropped; a value that fails its
# validator is dropped too (the event still counts).
PROPS: Dict[str, Dict[str, Callable[[Any], bool]]] = {
    "app_install": {"app_version": _short_str, "locale": _short_str},
    "app_launch": {"app_version": _short_str, "locale": _short_str},
    "directions_start": {"mode": _one_of(*MODES)},
    "sign_in": {"provider": _one_of(*PROVIDERS), "new_user": _flag},
    "route_created": {"version": _small_int, "days": _small_int, "places": _small_int},
    "place_shown": {"version": _small_int},
    "trip_downloaded": {"version": _small_int},
    # Ш-56: which known place outside the v1 area was asked for (an id of `planner.outside`);
    # written without user, install or trip, and without the tourist's words
    "wish_outside_area": {"place": _one_of(*OUTSIDE_IDS)},
}
# Which events may carry a place_id from the client.
CLIENT_PLACE_EVENTS = ("directions_start",)


def clean_props(name: str, raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Only whitelisted keys with valid scalar values; everything else is silently dropped."""
    allowed = PROPS.get(name, {})
    return {k: v for k, v in (raw or {}).items() if k in allowed and allowed[k](v)}
