"""User content API (Ш-44, SSOT §10). Prefix /v1, bearer auth except the public reviews list.

POST /uploads            {"content_type": "image/jpeg|png|webp", "size_bytes": n}
    -> 201 {"upload_id", "url", "method": "PUT", "headers": {...}, "expires_at", "max_bytes"}
    The client strips EXIF/GPS and compresses, then PUTs the bytes to `url` with exactly
    those headers and exactly `size_bytes` bytes. 503 `storage_unavailable` without storage.
POST /submissions        {"type": "review|menu|photo|transit|price", "place_id": uuid|null,
                          "payload": {...}}   (payloads: app/submissions/schemas.py)
    -> 201 {"id", "type", "place", "status", "pending_review", "reason_codes", "payload",
            "photo_url", "created_at", "decided_at"}
    Passed the auto-filter -> `published_pending_review` ("will be checked later", SSOT
    §10.2); garbage -> `rejected_auto` with `reason_codes` (still 201: it was received).
GET  /me/submissions?limit&cursor -> {"items": [same shape], "next_cursor"}
GET  /places/{id}/reviews?limit&cursor   (public)
    -> {"items": [{"id","rating","text","author_name","created_at","pending_review"}],
        "next_cursor", "summary": {"count", "average"}}
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from app.auth import sessions
from app.auth.api import bearer_token
from app.errors import AppError
from app.i18n import pick_locale
from app.providers.storage import StorageProvider, make_storage
from app.submissions import bonuses, service
from app.submissions.schemas import SubmissionIn, UploadIn

log = logging.getLogger("app.submissions")
router = APIRouter(prefix="/v1", tags=["submissions"])

NO_STORE = {"Cache-Control": "no-store"}


def get_storage(request: Request) -> StorageProvider:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        storage = make_storage()
        request.app.state.storage = storage
    if storage is None:
        raise AppError(503, "storage_unavailable")
    return storage


@router.post("/uploads", status_code=201)
async def create_upload(payload: UploadIn, request: Request):
    access = bearer_token(request)
    storage = get_storage(request)
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        body = await service.create_upload(
            conn, storage, user["id"], payload.content_type, payload.size_bytes
        )
    return JSONResponse(body, status_code=201, headers=NO_STORE)


@router.post("/submissions", status_code=201)
async def create_submission(payload: SubmissionIn, request: Request):
    access = bearer_token(request)
    locale = pick_locale(request.headers.get("accept-language"))
    if payload.type != "transit" and payload.place_id is None:
        raise AppError(422, "validation_error", "place_id is required")
    clean = service.parse_payload(payload.type, payload.payload)
    upload_id = clean.pop("upload_id", None)
    storage = get_storage(request) if upload_id else None
    upload, content_hash = None, None

    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        if payload.place_id is not None and not await service.place_exists(conn, payload.place_id):
            raise AppError(404, "not_found")
        if upload_id:
            upload = await service.load_upload(conn, user["id"], UUID(upload_id))
    if upload is not None:
        # The object is read outside any transaction (network I/O); a bad file rejects the slot.
        failure = None
        async with request.app.state.db.transaction() as conn:
            try:
                content_hash, _ = await service.verify_upload(conn, storage, upload)
            except AppError as exc:
                failure = exc  # swallowed so the transaction commits the slot's rejection
        if failure is not None:
            raise failure
    async with request.app.state.db.transaction() as conn:
        row = await service.create_submission(
            conn,
            user_id=user["id"],
            type_=payload.type,
            place_id=payload.place_id,
            payload=clean,
            locale=locale,
            upload=upload,
            content_hash=content_hash,
        )
    return JSONResponse(service.submission_json(row), status_code=201, headers=NO_STORE)


@router.get("/me/submissions")
async def my_submissions(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, max_length=200),
):
    access = bearer_token(request)
    locale = pick_locale(request.headers.get("accept-language"))
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await service.list_mine(conn, user["id"], locale, limit, cursor)


@router.get("/places/{place_id}/reviews")
async def place_reviews(
    place_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = Query(None, max_length=200),
):
    async with request.app.state.db.transaction() as conn:
        if not await service.place_exists(conn, place_id):
            raise AppError(404, "not_found")
        return await service.list_reviews(conn, place_id, limit, cursor)


@router.get("/me/bonuses")
async def my_bonuses(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, max_length=200),
):
    """Balance and history: {"balance", "tenge_per_bonus", "items": [{"id", "amount", "kind",
    "submission_id", "submission_type", "created_at"}], "next_cursor"} (Ш-46, SSOT §10.3).

    Bonuses are paid after a moderator approves a submission; spending is not available yet.
    """
    access = bearer_token(request)
    response.headers["Cache-Control"] = "no-store"
    async with request.app.state.db.transaction() as conn:
        user = await sessions.current_user(conn, access)
        return await bonuses.summary(conn, user["id"], limit, cursor)
