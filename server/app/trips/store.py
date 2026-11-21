"""SQL for trips (Ш-36). Raw, parameterized (SSOT §14.1). One trip per chat.

`save_plan` writes a whole `BuiltPlan` in the caller's transaction: the trip row (new, or the
chat's existing trip with `version + 1`), the main plan, the over-budget variants and the
lodging options. `apply_budget_choice` promotes a variant (SSOT §5.2, TECH_PLAN §2).
Readers of `trip_items` / `trip_legs` must filter `variant = 'main'`: that filter lives in ONE
place, `MAIN` and `main_items` / `main_legs` below (Ш-36 coordinator note, closed in Ш-37);
over-budget variants are read only through `variant_items`, for the budget section.
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


async def insert_leg(conn, trip_id: UUID, variant: str, leg, item_ids: Dict[UUID, UUID]) -> None:
    """Insert one leg; `item_ids` maps place id -> trip_items id of the leg's day."""
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
            await insert_leg(conn, trip_id, variant, leg, item_ids)
    return count


async def save_plan(
    conn,
    user_id: UUID,
    chat_id: UUID,
    plan: BuiltPlan,
    locale: str,
    weather_checked_at: Optional[Any] = None,
) -> Tuple[UUID, int, bool]:
    """Write the plan; returns (trip_id, version, created). Replaces an earlier plan of the chat.

    `weather_checked_at`: when the plan was built with a real forecast (Ш-40), that moment; None
    (no forecast) leaves the trip due for the re-check job at once.
    """
    brief = plan.brief
    row = await fetch_one(
        conn,
        """
        INSERT INTO trips (user_id, chat_id, brief, start_date, end_date, budget_kzt,
                           must_have_unmet, warnings, budget, total_cost_kzt, weather_checked_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chat_id) DO UPDATE SET
            version = trips.version + 1, brief = EXCLUDED.brief,
            start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date,
            budget_kzt = EXCLUDED.budget_kzt, must_have_unmet = EXCLUDED.must_have_unmet,
            warnings = EXCLUDED.warnings, budget = EXCLUDED.budget,
            total_cost_kzt = EXCLUDED.total_cost_kzt, budget_choice = NULL,
            weather_checked_at = EXCLUDED.weather_checked_at,
            status = 'active', updated_at = now()
        RETURNING id, version, (xmax = 0) AS created
        """,
        (
            user_id, chat_id, Jsonb(brief_json(dict(brief))), brief["start_date"],
            brief["end_date"], plan.budget_kzt, Jsonb(must_have_unmet_json(plan, locale)),
            Jsonb(warnings_json(plan)), Jsonb(budget_json(plan, locale, with_places=False)),
            plan.costs.total, weather_checked_at,
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


# --- readers (Ш-37, Ш-38) ---------------------------------------------------------------------
MAIN = "main"  # the plan; 'drop_places' / 'cheaper' are over-budget alternatives (SSOT §5.2)

_ITEM_COLUMNS = """
    i.id, i.day, i.ord, i.place_id, i.kind, i.meal, i.starts_at, i.ends_at, i.visit_min,
    i.is_must_have, i.est_cost_kzt, i.cost_assumed, i.hours_assumed, i.rain_exposed,
    p.name_ru, p.name_en, c.slug AS category, c.name_ru AS category_name_ru,
    c.name_en AS category_name_en, pc.slug AS parent_category,
    ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon,
    (SELECT ph.id FROM place_photos ph WHERE ph.place_id = p.id AND ph.status = 'approved'
     ORDER BY ph.created_at, ph.id LIMIT 1) AS photo_id,
    (SELECT ph.storage_key FROM place_photos ph WHERE ph.place_id = p.id
     AND ph.status = 'approved' ORDER BY ph.created_at, ph.id LIMIT 1) AS photo_key
"""

_ITEM_FROM = """
FROM trip_items i
JOIN places p ON p.id = i.place_id
LEFT JOIN place_categories c ON c.id = p.category_id
LEFT JOIN place_categories pc ON pc.id = c.parent_id
WHERE i.trip_id = %s AND i.variant = %s
ORDER BY i.day, i.ord
"""


async def variant_items(conn, trip_id: UUID, variant: str) -> List[dict]:
    """Items of one variant with their place; for the budget section only (use `main_items`)."""
    return await fetch_all(conn, "SELECT" + _ITEM_COLUMNS + _ITEM_FROM, (trip_id, variant))


async def main_items(conn, trip_id: UUID) -> List[dict]:
    """The plan's items (variant 'main') with place columns, ordered by day and `ord`."""
    return await variant_items(conn, trip_id, MAIN)


async def main_legs(conn, trip_id: UUID) -> List[dict]:
    """The plan's legs (variant 'main'); `day` is the day of the destination item."""
    return await fetch_all(
        conn,
        """
        SELECT l.id, l.from_item_id, l.to_item_id, l.depart_at, l.options, l.chosen_mode,
               l.travel_s, l.cost_kzt, l.estimated, i.day, i.ord
        FROM trip_legs l JOIN trip_items i ON i.id = l.to_item_id
        WHERE l.trip_id = %s AND l.variant = %s
        ORDER BY i.day, i.ord
        """,
        (trip_id, MAIN),
    )


async def offline_extras(conn, place_ids: List[UUID]) -> Tuple[Dict[UUID, dict], Dict[UUID, list]]:
    """Address columns and opening hours of the plan's places, for the offline copy (Ш-42)."""
    if not place_ids:
        return {}, {}
    places = await fetch_all(
        conn,
        "SELECT id, name_kk, address_ru, address_en FROM places WHERE id = ANY(%s)",
        (place_ids,),
    )
    hours = await fetch_all(
        conn,
        "SELECT place_id, weekday, opens, closes FROM place_hours "
        "WHERE place_id = ANY(%s) ORDER BY place_id, weekday, opens",
        (place_ids,),
    )
    by_hours: Dict[UUID, list] = {}
    for row in hours:
        by_hours.setdefault(row["place_id"], []).append(
            (row["weekday"], row["opens"], row["closes"])
        )
    return {row["id"]: row for row in places}, by_hours


async def get_trip_row(conn, user_id: UUID, trip_id: UUID, lock: bool = False) -> Optional[dict]:
    """The user's trip (foreign and missing look the same: None); `lock` = FOR UPDATE."""
    return await fetch_one(
        conn,
        "SELECT id, chat_id, user_id, brief, start_date, end_date, budget_kzt, status, version, "
        "weather_checked_at, must_have_unmet, warnings, budget, total_cost_kzt, budget_choice, "
        "created_at, updated_at FROM trips WHERE id = %s AND user_id = %s"
        + (" FOR UPDATE" if lock else ""),
        (trip_id, user_id),
    )


async def lodging_options(conn, trip_id: UUID) -> List[dict]:
    """Lodging options with the place columns the client shows, best rank first."""
    return await fetch_all(
        conn,
        """
        SELECT o.place_id, o.rank, o.price_per_night_kzt, o.price_assumed, o.nights, o.total_kzt,
               o.recommended, p.name_ru, p.name_en, c.slug AS category,
               ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lon
        FROM trip_lodging_options o
        JOIN places p ON p.id = o.place_id
        LEFT JOIN place_categories c ON c.id = p.category_id
        WHERE o.trip_id = %s ORDER BY o.rank
        """,
        (trip_id,),
    )


async def replace_day(conn, trip_id: UUID, day: date, plan) -> Dict[UUID, UUID]:
    """Ш-38: make the main plan's `day` equal to `plan` (a `DayPlan`) without touching other days.

    Items of places that stay keep their ids (clients hold them); stops of new places are
    inserted, items of places that left are deleted. Legs of the day are rebuilt (new ids).
    Returns place id -> item id for the day's items.
    """
    old = await fetch_all(
        conn,
        "SELECT id, place_id FROM trip_items WHERE trip_id = %s AND variant = %s AND day = %s "
        "ORDER BY ord",
        (trip_id, MAIN, day),
    )
    old_ids = [r["id"] for r in old]
    await execute(
        conn,
        "DELETE FROM trip_legs WHERE trip_id = %s AND to_item_id = ANY(%s)",
        (trip_id, old_ids),
    )
    # (trip_id, variant, day, ord) is unique: park the old ords out of the way first
    await execute(conn, "UPDATE trip_items SET ord = ord + 1000 WHERE id = ANY(%s)", (old_ids,))
    free: Dict[UUID, List[UUID]] = {}
    for r in old:
        free.setdefault(r["place_id"], []).append(r["id"])
    item_ids: Dict[UUID, UUID] = {}
    used: List[UUID] = []
    for ord_, stop in enumerate(plan.stops, start=1):
        kzt, assumed = bud.stop_cost(stop)
        reuse = free.get(stop.place.id)
        if reuse:
            item_id = reuse.pop(0)
            await execute(
                conn,
                """
                UPDATE trip_items SET ord = %s, kind = %s, meal = %s, starts_at = %s, ends_at = %s,
                    visit_min = %s, is_must_have = %s, est_cost_kzt = %s, cost_assumed = %s,
                    hours_assumed = %s, rain_exposed = %s
                WHERE id = %s
                """,
                (
                    ord_, stop.kind, stop.meal, stop.start, stop.end, stop.visit_min,
                    stop.must_have, kzt, assumed, stop.hours_assumed, stop.rain_exposed, item_id,
                ),
            )  # fmt: skip
        else:
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
                    trip_id, MAIN, day, ord_, stop.place.id, stop.kind, stop.meal, stop.start,
                    stop.end, stop.visit_min, stop.must_have, kzt, assumed, stop.hours_assumed,
                    stop.rain_exposed,
                ),
            )  # fmt: skip
            item_id = row["id"]
        item_ids[stop.place.id] = item_id
        used.append(item_id)
    leftover = [i for i in old_ids if i not in used]
    if leftover:
        await execute(conn, "DELETE FROM trip_items WHERE id = ANY(%s)", (leftover,))
    for leg in plan.legs:
        await insert_leg(conn, trip_id, MAIN, leg, item_ids)
    return item_ids


async def list_trips(conn, user_id: UUID, limit: int, before: Optional[Any] = None) -> List[dict]:
    """The user's trips, most recently updated first; `before` = updated_at of the last item."""
    return await fetch_all(
        conn,
        "SELECT id, chat_id, start_date, end_date, budget_kzt, status, version, budget, "
        "total_cost_kzt, updated_at FROM trips WHERE user_id = %s "
        "AND (%s::timestamptz IS NULL OR updated_at < %s::timestamptz) "
        "ORDER BY updated_at DESC, id LIMIT %s",
        (user_id, before, before, limit),
    )
