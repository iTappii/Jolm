"""What the live-plan jobs need from the outside, replaceable in tests.

The worker has no `app.state`: the weather provider is built on first use from the settings and
the worker's database, the router and the push provider likewise. Tests call `configure(...)`
with fakes (and `reset()`), so no test ever reaches Open-Meteo, Valhalla or APNs.
"""

from typing import Any, Optional

from app.config import get_settings
from app.push import make_push
from app.routing import make_router

_weather: Any = None
_router: Any = None
_push: Any = None
_own_weather = False


def configure(weather: Any = None, router: Any = None, push: Any = None) -> None:
    global _weather, _router, _push
    _weather, _router, _push = weather or _weather, router or _router, push or _push


def reset() -> None:
    global _weather, _router, _push, _own_weather
    _weather = _router = _push = None
    _own_weather = False


def weather(db: Any) -> Any:
    global _weather, _own_weather
    if _weather is None:
        from app.providers.weather import OpenMeteoProvider

        _weather = OpenMeteoProvider.from_settings(db)
        _own_weather = True
    return _weather


def router() -> Any:
    global _router
    if _router is None:
        _router = make_router(get_settings().valhalla_url)
    return _router


def push() -> Any:
    global _push
    if _push is None:
        _push = make_push(get_settings())
    return _push


def optional_weather() -> Optional[Any]:
    return _weather
