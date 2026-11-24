"""Ш-62: legs between far points when ONE day is timed again (edits of a built trip, Ш-38).

The trip generator (`planner.country`) builds the legs of an outing or a transfer from
`intercity.service`. An edit re-times a day with `planner.layout.retime_day`, which asks a
`LegProvider` for every transition: the city options would turn a 200 km road into a city leg and
the trip would lose `Leg.intercity`. `IntercityLegs` wraps the city provider: a pair of points at
least `min_distance_km` apart gets the options of the intercity service (the default one picked by
the same rule as the generator), and `intercity_of` returns the `intercity` block of the leg once
the default mode is known (it may be the mode the person chose, `PreferredLegs`).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.db import fetch_all
from app.planner import country as ctry
from app.planner.travel import LegProvider
from app.regions import default_region
from app.routing.base import Point, RoutingProvider, RoutingUnavailable
from app.routing.costs import IntercityParams
from app.routing.schemas import DirectionOption


class IntercityLegs:
    def __init__(
        self,
        inner: LegProvider,
        conn: Any,
        router: RoutingProvider,
        params: IntercityParams,
        settings: ctry.Settings,
        budget_kzt: Optional[int],
    ) -> None:
        self.inner, self.conn, self.router = inner, conn, router
        self.params, self.settings, self.budget_kzt = params, settings, budget_kzt
        self.tariffs = getattr(inner, "tariffs", {})
        self._raw: Dict[Tuple[Point, Point], List[Dict[str, Any]]] = {}

    def is_far(self, a: Point, b: Point) -> bool:
        return ctry.km(a, b) >= self.params.min_distance_km

    async def options(
        self, origin: Point, destination: Point, depart_at: datetime
    ) -> List[DirectionOption]:
        if not self.is_far(origin, destination):
            return await self.inner.options(origin, destination, depart_at)
        from app.intercity.service import intercity_options  # late: imports the routing service

        try:
            raw = await intercity_options(
                self.conn, self.router, self.tariffs, self.params, origin, destination,
                depart_at.date(), "ru", depart_at,
            )  # fmt: skip
        except RoutingUnavailable:
            raw = []
        if not raw:  # nothing known for this pair: the city options decide, as before Ш-62
            return await self.inner.options(origin, destination, depart_at)
        self._raw[(origin, destination)] = raw
        transfer = ctry.km(origin, destination) >= self.settings.transfer_min_km
        cap = (self.budget_kzt or 0) * self.settings.transfer_budget_share or float("inf")
        chosen = ctry.rank_options(raw, transfer, cap)[0]
        return [ctry._direction_option(o, origin, destination, o is chosen, depart_at) for o in raw]

    async def intercity_of(
        self, origin: Point, destination: Point, mode: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """The `Leg.intercity` block for the option of `mode` of the last `options` call."""
        raw = self._raw.get((origin, destination))
        if not raw or mode is None:
            return None
        option = next((o for o in raw if o["mode"] == mode), None)
        if option is None:
            return None
        return {
            "mode": option["mode"],
            "from_city": await self._label(origin),
            "to_city": await self._label(destination),
            "approximate": bool(option["approximate"]),
            "price_kzt_min": option["cost_kzt_min"],
            "price_kzt_max": option["cost_kzt_max"],
        }

    async def _label(self, point: Point) -> Dict[str, str]:
        """{ru, en} of the town around the point: the home city near it, else the nearest hub."""
        region = default_region()
        home = {"ru": region.name_ru, "en": region.name_en}
        if ctry.km(point, region.centre) <= self.settings.local_radius_km:
            return home
        rows = await fetch_all(self.conn, ctry.CITY_LABEL, {"lat": point[0], "lon": point[1]})
        return {"ru": rows[0]["city_ru"], "en": rows[0]["city_en"]} if rows else home
