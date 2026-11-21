"""Moderation of published submissions (Ш-45, SSOT §10.2).

Everything that passed the auto-filter is already visible (reviews, photos) or waiting (menus,
prices, transit data) as `published_pending_review`. A moderator approves or rejects it:

- approve -> `approved`. Menu and entry-price submissions are applied to the place now (they are
  not shown to others before a human has seen them, because they would overwrite facts); an
  adult entry price also protects `entry_price_kzt` from the OSM importer via `manual_override`.
  Transit data is only marked approved: there is no safe automatic mapping onto routes and stops,
  the team reads it from the table. Reviews and photos need nothing more.
- reject -> `rejected`. A rejected review disappears from the card; a rejected photo gets
  `place_photos.status = 'rejected'` and its file is queued for deletion.
An approval pays the bonus (Ш-46, bonuses.py); a rejection pays nothing.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import execute, fetch_all, fetch_one
from app.submissions import bonuses, service

PAGE = 50

QUEUE = """
SELECT s.id, s.type, s.payload, s.filter_result, s.created_at, s.place_id, s.user_id,
       p.name_ru, p.name_en, p.entry_price_kzt
FROM submissions s LEFT JOIN places p ON p.id = s.place_id
WHERE s.status = 'published_pending_review'
ORDER BY s.created_at, s.id
LIMIT %s
"""
QUEUE_SIZE = "SELECT count(*) AS n FROM submissions WHERE status = 'published_pending_review'"
DECIDE = """
UPDATE submissions SET status = %s, moderator_id = %s, decided_at = now()
WHERE id = %s AND status = 'published_pending_review'
RETURNING id, user_id, type, place_id, payload, place_photo_id
"""
MENU_UPSERT = """
INSERT INTO place_menu (place_id, payload, source) VALUES (%s, %s, 'user')
ON CONFLICT (place_id) DO UPDATE SET payload = EXCLUDED.payload, source = 'user', updated_at = now()
"""
ENTRY_PRICE = """
UPDATE places SET entry_price_kzt = %s, data_updated_at = now(),
    manual_override = (
        SELECT coalesce(jsonb_agg(DISTINCT v), '[]'::jsonb)
        FROM jsonb_array_elements(manual_override || '["entry_price_kzt"]'::jsonb) AS v)
WHERE id = %s
"""


class AlreadyDecided(Exception):
    """The submission is not in the queue any more (decided by someone else, or never was)."""


async def queue(conn) -> Dict[str, Any]:
    rows = await fetch_all(conn, QUEUE, (PAGE,))
    for r in rows:
        r["photo_key"] = r["payload"].get("photo_key")
        r["reasons"] = (r["filter_result"] or {}).get("reasons", [])
    return {"rows": rows, "total": (await fetch_one(conn, QUEUE_SIZE))["n"]}


async def decide(conn, admin_id: str, submission_id: UUID, approve: bool) -> Dict[str, Any]:
    row = await fetch_one(
        conn, DECIDE, ("approved" if approve else "rejected", admin_id, submission_id)
    )
    if row is None:
        raise AlreadyDecided()
    payload: Dict[str, Any] = row["payload"]
    if approve:
        # Paid after the human approval only, and measured before the content is applied (the
        # data age must not include the very submission being paid for).
        row["bonus"] = await bonuses.accrue(conn, row)
        await _apply(conn, row)
    else:
        keys: List[str] = []
        if row["place_photo_id"] is not None:
            await execute(
                conn,
                "UPDATE place_photos SET status = 'rejected' WHERE id = %s",
                (row["place_photo_id"],),
            )
        if payload.get("photo_key"):
            keys.append(payload["photo_key"])
        await service.enqueue_storage_delete(conn, keys, "storage.delete:sub:%s" % submission_id)
    return row


async def _apply(conn, row: Dict[str, Any]) -> None:
    payload: Optional[Dict[str, Any]] = row["payload"]
    if row["type"] == "menu" and row["place_id"] is not None:
        menu = {"items": payload.get("items", [])}
        if payload.get("photo_key"):
            menu["photo_key"] = payload["photo_key"]
        await execute(conn, MENU_UPSERT, (row["place_id"], Jsonb(menu)))
    elif row["type"] == "price" and payload.get("audience", "adult") == "adult":
        await execute(conn, ENTRY_PRICE, (payload["price_kzt"], row["place_id"]))
