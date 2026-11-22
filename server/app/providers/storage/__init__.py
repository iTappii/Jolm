"""Object storage for user photos (Ш-44, TECH_PLAN §3): S3-compatible, presigned uploads.

The API never receives image bytes on the upload path: `POST /v1/uploads` hands the client a
presigned PUT URL, the client uploads straight to the bucket, and the API later *reads* the
object back once (`StorageProvider.read`) to check that it is an image and to hash it.

Adapters:
- `S3Storage` (`STORAGE_PROVIDER=s3`): any S3-compatible service (MinIO in dev, see
  `infra/docker-compose.yml`, or a cloud bucket in prod); SigV4 presigning done by hand so no
  AWS SDK is needed.
- `LocalStorage` (`STORAGE_PROVIDER=local`): dev/test only, files on disk and an upload endpoint
  in this API; for working without Docker.
Empty `STORAGE_PROVIDER` = no storage: uploads answer 503 `storage_unavailable`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Protocol

from app.config import Settings, get_settings


class StorageError(Exception):
    """The storage backend failed or was unreachable (retryable)."""


class ObjectTooLarge(Exception):
    """The stored object is larger than the limit it was read with."""


@dataclass(frozen=True)
class PresignedPut:
    url: str
    method: str
    headers: Dict[str, str]  # headers the client MUST send unchanged
    expires_at: datetime


class StorageProvider(Protocol):
    def presign_put(
        self, key: str, content_type: str, size_bytes: int, expires_sec: int
    ) -> PresignedPut:
        """Presigned URL for one PUT of exactly `size_bytes` with this content type."""

    async def put(self, key: str, content_type: str, data: bytes) -> None:
        """Store `data` from the server itself (admin uploads, Ш-55); `StorageError` on failure."""

    async def read(self, key: str, max_bytes: int) -> Optional[bytes]:
        """The whole object, None when it does not exist; `ObjectTooLarge` above `max_bytes`."""

    async def delete(self, key: str) -> None:
        """Remove an object; a missing one is not an error."""

    async def aclose(self) -> None: ...


def media_url(key: Optional[str], base: Optional[str] = None) -> Optional[str]:
    """Public URL of a stored object: `MEDIA_BASE_URL/<key>`; None without a key or a base."""
    if not key:
        return None
    base = (get_settings().media_base_url if base is None else base).strip().rstrip("/")
    return "%s/%s" % (base, key.lstrip("/")) if base else None


def make_storage(settings: Optional[Settings] = None) -> Optional[StorageProvider]:
    settings = settings or get_settings()
    kind = settings.storage_provider.strip().lower()
    if kind == "s3":
        from app.providers.storage.s3 import S3Storage

        return S3Storage.from_settings(settings)
    if kind == "local":
        if settings.app_env not in ("dev", "test"):
            return None  # the local adapter is never used outside dev/test
        from app.providers.storage.local import LocalStorage

        return LocalStorage.from_settings(settings)
    return None
