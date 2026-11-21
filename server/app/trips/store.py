"""SQL for trips (Ш-36). Raw, parameterized (SSOT §14.1). One trip per chat.

`save_plan` writes a whole `BuiltPlan` in the caller's transaction: the trip row (new, or the
chat's existing trip with `version + 1`), the main plan, the over-budget variants and the
lodging options. `apply_budget_choice` promotes a variant (SSOT §5.2, TECH_PLAN §2).
Readers of `trip_items` / `trip_legs` must filter `variant = 'main'`.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import execute, fetch_all, fetch_one
from app.planner import budget as bud
from app.planner.build import (
    BuiltPlan,
    budget_json,
    must_have_unmet_json,
    warnings_json,
)
from app.planner.layout import TripLayout

CHOICES = ("drop_places", "cheaper", "keep")


def brief_json(brief: Dict[str, Any]) -> Dict[str, Any]:
    """The brief as stored with the trip: ISO dates, plain lists."""
    out = dict(brief)
    for key in ("start_date", "end_date"):
        if isinstance(out.get(key), date):
            out[key] = out[key].isoformat()
    out["must_haves"] = list(out.get("must_haves") or [])
    out["interests"] = list(out.get("interests") or [])
    return out


async def write_layout(conn, trip_id: UUID, variant: str, layout: TripLayout) -> int:
    """Insert items and legs of one layout; returns the number of items."""
    count = 0
    for day in layout.days:
        item_ids: Dict[UUID, UUID] = {}
        for ord_, stop in enumerate(day.stops, start=1):
            kzt, assumed = bud.stop_cost(stop)
            row = await fetch_one(
                conn,
                """
                INSERT INTO trip_items
                    (trip_id, variant, day, ord, place_id, kind, meal, starts_at, ends_at,
                     visit_min, is_must_have, est_cost_kzt, cost_assumed, hours_assumed,
                     rain_exposed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    trip_id, variant, day.date, ord_, stop.place.id, stop.kind, stop.meal,
                    stop.start, stop.end, stop.visit_min, stop.must_have, kzt, assumed,
                    stop.hours_assumed, stop.rain_exposed,
                ),
            )  # fmt: skip
            item_ids[stop.place.id] = row["id"]
            count += 1
        for leg in day.legs:
            options = [o.model_dump(exclude_none=True, exclude={"steps"}) for o in leg.options]
            await execute(
                conn,
                """
                INSERT INTO trip_legs
                    (trip_id, variant, from_item_id, to_item_id, depart_at, options, chosen_mode,
                     travel_s, cost_kzt, estimated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    trip_id, variant,
                    item_ids.get(leg.origin_place_id) if leg.origin_place_id else None,
                    item_ids[leg.destination_place_id], leg.depart_at, Jsonb(options),
                    leg.default_mode, int(round(leg.travel_s)), bud.leg_cost(leg), leg.estimated,
                ),
            )  # fmt: skip
    return count


async def save_plan(
    conn, user_id: UUID, chat_id: UUID, plan: BuiltPlan, locale: str
) -> Tuple[UUID, int, bool]:
    """Write the plan; returns (trip_id, version, created). Replaces an earlier plan of the chat."""
    brief = plan.brief
    row = await fetch_one(
        conn,
        """
        INSERT INTO trips (user_id, chat_id, brief, start_date, end_date, budget_kzt,
                           must_have_unmet, warnings, budget, total_cost_kzt)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chat_id) DO UPDATE SET
            version = trips.version + 1, brief = EXCLUDED.brief,
            start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
            budget_kzt = EXCLUDED.budget_kzt, must_have_unmet = EXCLUDED.must_have_unmet,
            warnings = EXCLUDED.warnings, budget = EXCLUDED.budget,
            total_cost_kzt = EXCLUDED.total_cost_kzt, budget_choice = NULL,
            status = 'active', updated_at = now()
        RETURNING id, version, (xmax = 0) AS created
        """,
        (
            user_id, chat_id, Jsonb(brief_json(dict(brief))), brief["start_date"],
            brief["end_date"], plan.budget_kzt, Jsonb(must_have_unmet_json(plan, locale)),
            Jsonb(warnings_json(plan)), Jsonb(budget_json(plan, locale, with_places=False)),
            plan.costs.total,
        ),
    )  # fmt: skip
    trip_id = row["id"]
    await execute(conn, "DELETE FROM trip_items WHERE trip_id = %s", (trip_id,))  # legs cascade
    await execute(conn, "DELETE FROM trip_lodging_options WHERE trip_id = %s", (trip_id,))
    await write_layout(conn, trip_id, "main", plan.layout)
    for variant in plan.variants:
        await write_layout(conn, trip_id, variant.kind, variant.layout)
    for option in plan.lodging.options:
        await execute(
            conn,
            """
            INSERT INTO trip_lodging_options
                (trip_id, place_id, rank, price_per_night_kzt, price_assumed, nights, total_kzt,
                 recommended)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                trip_id, option.place.id, option.rank, option.price, option.assumed,
                plan.lodging.nights, option.total, option.recommended,
            ),
        )  # fmt: skip
    return trip_id, row["version"], bool(row["created"])


async def get_trip_for_update(conn, user_id: UUID, trip_id: UUID) -> Optional[dict]:
    """The trip only if it is the user's (a foreign or missing id is the same: None)."""
    return await fetch_one(
        conn,
        "SELECT id, version, budget, warnings, budget_choice FROM trips "
        "WHERE id = %s AND user_id = %s FOR UPDATE",
        (trip_id, user_id),
    )


def resolved_budget(budget: Dict[str, Any], choice: str) -> Dict[str, Any]:
    """The stored budget block after `choice`: the variant's numbers become the plan's."""
    out = dict(budget)
    variant = (budget.get("variants") or {}).get(choice)
    if variant is not None:
        total = variant["total_kzt"]
        out.update(
            total_kzt=total,
            remaining_kzt=budget["budget_kzt"] - total,
            shortfall_kzt=max(0, total - budget["budget_kzt"]),
            breakdown=variant["breakdown"],
            status="ok" if total <= budget["budget_kzt"] else "over",
        )
        lodging = dict(budget["lodging"])
        if choice == "cheaper" and variant.get("lodging_changed"):
            lodging["cost_kzt"] = variant["lodging_total_kzt"]
        out["lodging"] = lodging
    out["variants"] = None
    out["choice"] = choice
    return out


async def apply_budget_choice(conn, trip: dict, choice: str) -> Dict[str, Any]:
    """Make `choice` the plan: a variant's rows become 'main', the rest are deleted.

    `keep` accepts the plan over budget. Returns the new stored budget block. The caller has
    checked that a choice is open (status over, variants present, no choice yet).
    """
    trip_id = trip["id"]
    budget = resolved_budget(trip["budget"], choice)
    if choice != "keep":
        await execute(
            conn, "DELETE FROM trip_items WHERE trip_id = %s AND variant = 'main'", (trip_id,)
        )  # main legs cascade
        for table in ("trip_items", "trip_legs"):
            await execute(
                conn,
                "UPDATE %s SET variant = 'main' WHERE trip_id = %%s AND variant = %%s" % table,  # noqa: S608
                (trip_id, choice),
            )  # table name from the fixed tuple above, never from input
        if choice == "cheaper" and (trip["budget"]["variants"][choice].get("lodging_changed")):
            await execute(
                conn, "UPDATE trip_lodging_options SET recommended = false WHERE trip_id = %s",
                (trip_id,),
            )  # fmt: skip
            await execute(
                conn,
                """
                UPDATE trip_lodging_options SET recommended = true
                WHERE trip_id = %s AND place_id = (
                    SELECT place_id FROM trip_lodging_options WHERE trip_id = %s
                    ORDER BY total_kzt, rank LIMIT 1)
                """,
                (trip_id, trip_id),
            )
    await execute(
        conn,
        "DELETE FROM trip_items WHERE trip_id = %s AND variant <> 'main'",
        (trip_id,),
    )
    warnings: List[dict] = list(trip["warnings"])
    if budget["status"] == "ok":
        warnings = [w for w in warnings if w["code"] != "over_budget"]
    await execute(
        conn,
        """
        UPDATE trips SET budget = %s, warnings = %s, total_cost_kzt = %s, budget_choice = %s,
                         version = version + 1, updated_at = now()
        WHERE id = %s
        """,
        (Jsonb(budget), Jsonb(warnings), budget["total_kzt"], choice, trip_id),
    )
    return budget


async def lodging_rows(conn, trip_id: UUID) -> List[dict]:
    return await fetch_all(
        conn,
        "SELECT place_id, rank, price_per_night_kzt, price_assumed, nights, total_kzt, recommended "
        "FROM trip_lodging_options WHERE trip_id = %s ORDER BY rank",
        (trip_id,),
    )
