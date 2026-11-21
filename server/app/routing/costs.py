"""Versioned transport tariffs and pure direction cost and ranking rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional, Sequence

from psycopg import AsyncConnection

from app.db import fetch_all


@dataclass(frozen=True)
class Tariff:
    mode: str
    base_kzt: Decimal
    per_min_kzt: Decimal
    per_km_kzt: Decimal
    approximate: bool = True


async def load_tariffs(conn: AsyncConnection, travel_date: date) -> dict[str, Tariff]:
    rows = await fetch_all(
        conn,
        """
        SELECT DISTINCT ON (mode) mode, base_kzt, per_min_kzt, per_km_kzt, approximate
        FROM transport_tariffs
        WHERE valid_from <= %s
        ORDER BY mode, valid_from DESC, version_id DESC
        """,
        (travel_date,),
    )
    return {row["mode"]: Tariff(**row) for row in rows}


def calculate_cost(
    tariff: Tariff, distance_m: float, duration_s: float, traffic_max: float = 1.0
) -> tuple[int, int]:
    """Round cost bounds to whole tenge and apply the approximate traffic factor."""
    if tariff.mode == "walk":
        return (0, 0)
    minutes = Decimal(str(duration_s)) / 60
    kilometers = Decimal(str(distance_m)) / 1000
    cost = tariff.base_kzt + tariff.per_min_kzt * minutes + tariff.per_km_kzt * kilometers
    high = cost * Decimal(str(traffic_max))
    return (
        int(cost.to_integral_value(rounding=ROUND_HALF_UP)),
        int(high.to_integral_value(rounding=ROUND_HALF_UP)),
    )


def recommend(options: Sequence[Mapping[str, Any]]) -> Optional[int]:
    """Prefer walks up to 15 minutes, then rank by time plus 1 second per tenge."""
    return min(
        range(len(options)),
        key=lambda index: _recommendation_rank(options[index]),
        default=None,
    )


def _recommendation_rank(option: Mapping[str, Any]) -> tuple[bool, float, float, int]:
    duration = option["duration_s"]
    cost = option["cost_kzt_max"]
    short_walk = option["mode"] == "walk" and duration <= 15 * 60
    return (not short_walk, duration + cost, duration, cost)
