"""Bonus accrual and reading (Ш-46, SSOT §10.3). The formula is in bonus_policy.py."""

from typing import Any, Dict, Optional
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import execute, fetch_all, fetch_one
from app.submissions import bonus_policy
from app.submissions.service import decode_cursor, encode_cursor

# Age in days of the field a submission improves, measured BEFORE the approval applies it and
# without the submission's own rows. params: place_id, submission id / photo id.
_AGE = "EXTRACT(EPOCH FROM now() - {col}) / 86400.0"
FIELD_AGE = {
    "review": "SELECT " + _AGE.format(col="max(created_at)") + " AS age FROM submissions"
    " WHERE place_id = %(place)s AND type = 'review' AND id <> %(sub)s"
    " AND status IN ('published_pending_review', 'approved')",
    "photo": "SELECT " + _AGE.format(col="max(created_at)") + " AS age FROM place_photos"
    " WHERE place_id = %(place)s AND status = 'approved' AND id IS DISTINCT FROM %(photo)s",
    "menu": "SELECT " + _AGE.format(col="max(updated_at)") + " AS age FROM place_menu"
    " WHERE place_id = %(place)s",
    "price": "SELECT " + _AGE.format(col="max(data_updated_at)") + " AS age FROM places"
    " WHERE id = %(place)s",
}
TRIPS_WITH_PLACE = """
SELECT count(DISTINCT t.id) AS n
FROM trip_items ti JOIN trips t ON t.id = ti.trip_id
WHERE ti.place_id = %s AND ti.variant = 'main'
  AND t.created_at > now() - make_interval(days => %s)
"""
INSERT_LEDGER = """
INSERT INTO bonus_ledger (user_id, amount, idempotency_key, submission_id, submission_type, details)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (idempotency_key) DO NOTHING
RETURNING id
"""
LIST = """
SELECT id, amount, kind, submission_type, submission_id, created_at
FROM bonus_ledger
WHERE user_id = %(user)s
  AND (%(ts)s::timestamptz IS NULL OR (created_at, id) < (%(ts)s, %(id)s))
ORDER BY created_at DESC, id DESC
LIMIT %(limit)s
"""
BALANCE = "SELECT coalesce(sum(amount), 0)::bigint AS balance FROM bonus_ledger WHERE user_id = %s"


async def load_coefficients(conn) -> Dict[str, float]:
    rows = await fetch_all(conn, "SELECT key, value FROM demand_coefficients")
    return bonus_policy.resolve({r["key"]: float(r["value"]) for r in rows})


async def accrue(conn, row: Dict[str, Any]) -> Optional[int]:
    """Pay the author of an APPROVED submission; returns the amount, or None when nothing is paid.

    `row` is the decided submission (id, user_id, type, place_id, place_photo_id). Called by the
    moderator's approval in the same transaction, before the content is applied to the place.
    Nothing is paid for rejected or auto-rejected content (the caller never gets here), for
    anonymized authors (deleted account) or when the amount is 0. The unique idempotency key makes
    a repeat harmless: one accrual per submission, ever.
    """
    if row["user_id"] is None:
        return None
    type_, place_id = row["type"], row["place_id"]
    age: Optional[float] = None
    trips = 0
    if type_ != "transit" and place_id is not None:
        found = await fetch_one(
            conn,
            FIELD_AGE[type_],
            {"place": place_id, "sub": row["id"], "photo": row.get("place_photo_id")},
        )
        age = float(found["age"]) if found and found["age"] is not None else None
    coeffs = await load_coefficients(conn)
    if type_ != "transit" and place_id is not None:
        trips = (
            await fetch_one(conn, TRIPS_WITH_PLACE, (place_id, int(coeffs["freq_window_days"])))
        )["n"]
    result = bonus_policy.compute(type_, coeffs, age, trips)
    if result.amount <= 0:
        return None
    inserted = await fetch_one(
        conn,
        INSERT_LEDGER,
        (
            row["user_id"],
            result.amount,
            "submission:%s" % row["id"],
            row["id"],
            type_,
            Jsonb(result.as_json(age, trips)),
        ),
    )
    return result.amount if inserted else None


async def summary(conn, user_id: UUID, limit: int, cursor: Optional[str]) -> Dict[str, Any]:
    ts, ident = decode_cursor(cursor)
    total = await fetch_one(conn, BALANCE, (user_id,))
    rows = await fetch_all(conn, LIST, {"user": user_id, "ts": ts, "id": ident, "limit": limit + 1})
    page = rows[:limit]
    return {
        "balance": total["balance"],
        "tenge_per_bonus": 1,  # SSOT §10.3: 1 bonus ~ 1 tenge; spending is not available yet
        "items": [
            {
                "id": str(r["id"]),
                "amount": r["amount"],
                "kind": r["kind"],
                "submission_id": str(r["submission_id"]) if r["submission_id"] else None,
                "submission_type": r["submission_type"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in page
        ],
        "next_cursor": (
            encode_cursor(page[-1]["created_at"], page[-1]["id"]) if len(rows) > limit else None
        ),
    }


async def save_coefficients(conn, admin_id: str, values: Dict[str, float]) -> None:
    for key, value in values.items():
        await execute(
            conn,
            "INSERT INTO demand_coefficients (key, value, updated_by) VALUES (%s, %s, %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now(),"
            " updated_by = EXCLUDED.updated_by",
            (key, value, admin_id),
        )
