from app.routing.base import (  # noqa: F401
    MODES,
    Maneuver,
    MatrixResult,
    NoRoute,
    Point,
    RouteResult,
    RoutingError,
    RoutingProvider,
    RoutingUnavailable,
)
from app.routing.fake import FakeRouter  # noqa: F401
from app.routing.transit import (  # noqa: F401
    TransitLeg,
    TransitNetwork,
    TransitOption,
    find_transit_options,
    get_network,
)
from app.routing.valhalla import ValhallaRouter  # noqa: F401


def make_router(valhalla_url=None) -> RoutingProvider:
    """ValhallaRouter if a URL is configured, else the offline FakeRouter (dev/tests)."""
    if valhalla_url:
        return ValhallaRouter(valhalla_url)
    return FakeRouter()
