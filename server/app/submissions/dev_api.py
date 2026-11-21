"""Dev/test only: the upload endpoint that `LocalStorage` presigned URLs point at."""

from fastapi import APIRouter, Request, Response

from app.errors import AppError
from app.providers.storage.local import LocalStorage

router = APIRouter(prefix="/v1", include_in_schema=False)


@router.put("/dev-uploads/{key:path}", status_code=200)
async def dev_upload(key: str, request: Request, size: int, exp: int, sig: str):
    storage = getattr(request.app.state, "storage", None)
    if not isinstance(storage, LocalStorage):
        raise AppError(404, "not_found")
    content_type = request.headers.get("content-type", "")
    if not storage.verify(key, content_type, size, exp, sig):
        raise AppError(403, "forbidden")
    body = await request.body()
    if len(body) != size:
        raise AppError(422, "validation_error", "body length differs from the signed size")
    storage.write(key, body)
    return Response(status_code=200)
