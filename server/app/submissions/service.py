"""User submissions: uploads, creation, listing (Ш-44, SSOT §10)."""

import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app import worker
from app.db import execute, fetch_all, fetch_one
from app.errors import AppError
from app.places import service as places_service
from app.providers.storage import ObjectTooLarge, StorageError, StorageProvider, media_url
from app.submissions import autofilter
from app.submissions.schemas import MODELS

log = logging.getLogger("app.submissions")

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # the client compresses long before this
PRESIGN_TTL_SEC = 15 * 60  # the PUT URL
UPLOAD_SLOT_TTL = timedelta(hours=1)  # time to attach an uploaded file to a submission
UPLOADS_PER_DAY = 40
SUBMISSIONS_PER_DAY = 30
PUBLISHED = ("published_pending_review", "approved")
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
STORAGE_DELETE_JOB = "storage.delete"


def sniff_image(data: bytes) -> Optional[str]:
    """Content type by magic bytes: JPEG, PNG or WebP only. The declared type is never trusted."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def enqueue_storage_delete(conn, keys: List[str], dedupe_key: str) -> None:
    if keys:
        await worker.enqueue(conn, STORAGE_DELETE_JOB, {"keys": keys}, dedupe_key=dedupe_key)


# --- uploads -----------------------------------------------------------------------------------


async def create_upload(
    conn, storage: StorageProvider, user_id: UUID, content_type: str, size_bytes: int
) -> Dict[str, Any]:
    if size_bytes > MAX_IMAGE_BYTES:
        raise AppError(422, "validation_error", "size_bytes is above %d" % MAX_IMAGE_BYTES)
    await fetch_one(conn, "SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
    recent = await fetch_one(
        conn,
        "SELECT count(*) AS n FROM uploads WHERE user_id = %s"
        " AND created_at > now() - interval '24 hours'",
        (user_id,),
    )
    if recent["n"] >= UPLOADS_PER_DAY:
        raise AppError(429, "rate_limited", headers={"Retry-After": "3600"})
    now = datetime.now(timezone.utc)
    # Random key: no user id, no place id, nothing guessable or personal in a public URL.
    key = "ugc/%s/%s.%s" % (now.strftime("%Y/%m"), uuid4().hex, EXTENSIONS[content_type])
    row = await fetch_one(
        conn,
        "INSERT INTO uploads (user_id, storage_key, content_type, size_bytes, expires_at)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (user_id, key, content_type, size_bytes, now + UPLOAD_SLOT_TTL),
    )
    put = storage.presign_put(key, content_type, size_bytes, PRESIGN_TTL_SEC)
    return {
        "upload_id": str(row["id"]),
        "url": put.url,
        "method": put.method,
        "headers": put.headers,
        "expires_at": put.expires_at.isoformat(),
        "max_bytes": MAX_IMAGE_BYTES,
    }


async def load_upload(conn, user_id: UUID, upload_id: UUID) -> Dict[str, Any]:
    row = await fetch_one(
        conn,
        "SELECT id, storage_key, content_type, size_bytes, status FROM uploads"
        " WHERE id = %s AND user_id = %s AND expires_at > now()",
        (upload_id, user_id),
    )
    if row is None:
        raise AppError(422, "upload_not_found")
    if row["status"] != "pending":
        raise AppError(409, "upload_used")
    return row


async def verify_upload(
    conn, storage: StorageProvider, upload: Dict[str, Any]
) -> Tuple[str, bytes]:
    """Read the uploaded object once: it must exist, fit, and be an image of the declared type.

    Returns (sha256 hex, bytes). A bad file marks the slot rejected and queues its deletion.
    """
    try:
        data = await storage.read(upload["storage_key"], MAX_IMAGE_BYTES)
    except ObjectTooLarge:
        data = b""
    except StorageError:
        log.exception("storage read failed")
        raise AppError(503, "storage_unavailable") from None
    if data is None:
        raise AppError(422, "upload_not_found")
    ok = len(data) == upload["size_bytes"] and sniff_image(data) == upload["content_type"]
    if not ok:
        await execute(conn, "UPDATE uploads SET status = 'rejected' WHERE id = %s", (upload["id"],))
        await enqueue_storage_delete(
            conn, [upload["storage_key"]], "storage.delete:%s" % upload["id"]
        )
        raise AppError(422, "invalid_image")
    return hashlib.sha256(data).hexdigest(), data


# --- submissions ---------------------------------------------------------------------------------


def parse_payload(type_: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validated payload of a submission as a JSON-ready dict."""
    from pydantic import ValidationError

    try:
        model = MODELS[type_](**raw)
    except (ValidationError, TypeError, ValueError):
        raise AppError(422, "validation_error") from None
    return model.model_dump(mode="json", exclude_none=True)


async def place_exists(conn, place_id: UUID) -> bool:
    row = await fetch_one(
        conn, "SELECT 1 AS ok FROM places WHERE id = %s AND status = 'active'", (place_id,)
    )
    return row is not None


async def create_submission(
    conn,
    *,
    user_id: UUID,
    type_: str,
    place_id: Optional[UUID],
    payload: Dict[str, Any],
    locale: str,
    upload: Optional[Dict[str, Any]],
    content_hash: Optional[str],
) -> Dict[str, Any]:
    await fetch_one(conn, "SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))
    recent = await fetch_one(
        conn,
        "SELECT count(*) AS n FROM submissions WHERE user_id = %s"
        " AND created_at > now() - interval '24 hours'",
        (user_id,),
    )
    if recent["n"] >= SUBMISSIONS_PER_DAY:
        raise AppError(429, "rate_limited", headers={"Retry-After": "3600"})
    if type_ == "review":
        again = await fetch_one(
            conn,
            "SELECT 1 AS ok FROM submissions WHERE user_id = %s AND place_id = %s"
            " AND type = 'review' AND status IN ('published_pending_review', 'approved')",
            (user_id, place_id),
        )
        if again:
            raise AppError(409, "already_submitted")
    if upload is not None:
        claimed = await execute(
            conn,
            "UPDATE uploads SET status = 'used' WHERE id = %s AND status = 'pending'",
            (upload["id"],),
        )
        if not claimed:
            raise AppError(409, "upload_used")
        payload = dict(payload, photo_key=upload["storage_key"])
    result = await autofilter.evaluate(
        conn, type=type_, payload=payload, user_id=user_id, place_id=place_id,
        content_hash=content_hash,
    )  # fmt: skip
    status = "published_pending_review" if result.passed else "rejected_auto"
    photo_id = None
    if upload is not None:
        if result.passed and type_ == "photo":
            # Published at once like the rest (SSOT §10.2); place_photos is what the card shows.
            row = await fetch_one(
                conn,
                "INSERT INTO place_photos (place_id, storage_key, source, author_user_id, status)"
                " VALUES (%s, %s, 'user', %s, 'approved') RETURNING id",
                (place_id, upload["storage_key"], user_id),
            )
            photo_id = row["id"]
        elif not result.passed:
            await enqueue_storage_delete(
                conn, [upload["storage_key"]], "storage.delete:%s" % upload["id"]
            )
    row = await fetch_one(
        conn,
        "INSERT INTO submissions (user_id, place_id, type, payload, status, filter_result,"
        " content_hash, place_photo_id, locale)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " RETURNING id, user_id, place_id, type, payload, status, filter_result, created_at,"
        " decided_at",
        (
            user_id, place_id, type_, Jsonb(payload), status, Jsonb(result.as_json()),
            content_hash, photo_id, locale,
        ),
    )  # fmt: skip
    return row


def submission_json(row: Dict[str, Any], place_name: Optional[str] = None) -> Dict[str, Any]:
    payload = dict(row["payload"])
    key = payload.pop("photo_key", None)
    reasons = (row["filter_result"] or {}).get("reasons", [])
    return {
        "id": str(row["id"]),
        "type": row["type"],
        "place": {"id": str(row["place_id"]), "name": place_name} if row["place_id"] else None,
        "status": row["status"],
        # SSOT §10.2: shown to everyone at once, "will be checked later" until a moderator decides
        "pending_review": row["status"] == "published_pending_review",
        "reason_codes": reasons if row["status"] == "rejected_auto" else [],
        "payload": payload,
        "photo_url": media_url(key) if key and row["status"] in PUBLISHED else None,
        "created_at": row["created_at"].isoformat(),
        "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
    }


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = "%s|%s" % (created_at.isoformat(), row_id)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: Optional[str]) -> Tuple[Optional[datetime], Optional[UUID]]:
    if not cursor:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, _, ident = raw.partition("|")
        return datetime.fromisoformat(stamp), UUID(ident)
    except (ValueError, UnicodeDecodeError):
        raise AppError(422, "validation_error", "Invalid cursor") from None


LIST_MINE = """
SELECT s.id, s.user_id, s.place_id, s.type, s.payload, s.status, s.filter_result, s.created_at,
       s.decided_at, p.name_ru, p.name_en, p.name_kk
FROM submissions s LEFT JOIN places p ON p.id = s.place_id
WHERE s.user_id = %(user)s
  AND (%(ts)s::timestamptz IS NULL OR (s.created_at, s.id) < (%(ts)s, %(id)s))
ORDER BY s.created_at DESC, s.id DESC
LIMIT %(limit)s
"""

LIST_REVIEWS = """
SELECT s.id, s.payload, s.status, s.created_at, u.display_name
FROM submissions s LEFT JOIN users u ON u.id = s.user_id
WHERE s.place_id = %(place)s AND s.type = 'review'
  AND s.status IN ('published_pending_review', 'approved')
  AND (%(ts)s::timestamptz IS NULL OR (s.created_at, s.id) < (%(ts)s, %(id)s))
ORDER BY s.created_at DESC, s.id DESC
LIMIT %(limit)s
"""

REVIEW_SUMMARY = """
SELECT count(*) AS n, avg((payload->>'rating')::int) AS avg
FROM submissions
WHERE place_id = %s AND type = 'review' AND status IN ('published_pending_review', 'approved')
"""


async def list_mine(conn, user_id: UUID, locale: str, limit: int, cursor: Optional[str]):
    ts, ident = decode_cursor(cursor)
    rows = await fetch_all(
        conn, LIST_MINE, {"user": user_id, "ts": ts, "id": ident, "limit": limit + 1}
    )
    page = rows[:limit]
    items = [submission_json(r, places_service.pick_text(r, "name", locale)[0] or "") for r in page]
    more = len(rows) > limit
    return {
        "items": items,
        "next_cursor": encode_cursor(page[-1]["created_at"], page[-1]["id"]) if more else None,
    }


async def list_reviews(conn, place_id: UUID, limit: int, cursor: Optional[str]):
    ts, ident = decode_cursor(cursor)
    rows = await fetch_all(
        conn, LIST_REVIEWS, {"place": place_id, "ts": ts, "id": ident, "limit": limit + 1}
    )
    summary = await fetch_one(conn, REVIEW_SUMMARY, (place_id,))
    page = rows[:limit]
    items = [
        {
            "id": str(r["id"]),
            "rating": r["payload"]["rating"],
            "text": r["payload"].get("text"),
            "author_name": r["display_name"],  # null for anonymous / deleted accounts
            "created_at": r["created_at"].isoformat(),
            "pending_review": r["status"] == "published_pending_review",
        }
        for r in page
    ]
    return {
        "items": items,
        "next_cursor": (
            encode_cursor(page[-1]["created_at"], page[-1]["id"]) if len(rows) > limit else None
        ),
        "summary": {
            "count": summary["n"],
            "average": round(float(summary["avg"]), 1) if summary["n"] else None,
        },
    }
