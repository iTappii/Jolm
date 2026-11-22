"""Dev/test storage on the local disk. NEVER for production (see `make_storage`).

The presigned URL points at this API (`PUT /v1/dev-uploads/<key>`, see `app/uploads/dev.py`),
protected by an HMAC over the key, content type, size and expiry; files are served from `/media`.
"""

import hashlib
import hmac
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.providers.storage import ObjectTooLarge, PresignedPut


def _sig(secret: str, key: str, content_type: str, size: int, expires: int) -> str:
    msg = "PUT\n%s\n%s\n%d\n%d" % (key, content_type, size, expires)
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


class LocalStorage:
    def __init__(self, root: Path, upload_base: str, secret: str) -> None:
        self.root = Path(root)
        self.upload_base = upload_base.rstrip("/")
        self.secret = secret

    @classmethod
    def from_settings(cls, s: Settings) -> "LocalStorage":
        root = s.storage_local_dir or str(Path(tempfile.gettempdir()) / "jol-media-dev")
        return cls(Path(root), s.storage_local_upload_base, s.auth_secret.get_secret_value())

    def path(self, key: str) -> Path:
        """File of a key; refuses anything that would leave `root`."""
        target = (self.root / key.lstrip("/")).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError("bad storage key")
        return target

    def presign_put(
        self, key: str, content_type: str, size_bytes: int, expires_sec: int
    ) -> PresignedPut:
        expires = int(time.time()) + expires_sec
        sig = _sig(self.secret, key, content_type, size_bytes, expires)
        url = "%s/v1/dev-uploads/%s?size=%d&exp=%d&sig=%s" % (
            self.upload_base, key, size_bytes, expires, sig,
        )  # fmt: skip
        return PresignedPut(
            url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
        )

    def verify(self, key: str, content_type: str, size: int, expires: int, sig: str) -> bool:
        good = _sig(self.secret, key, content_type, size, expires)
        return expires >= time.time() and hmac.compare_digest(good, sig)

    def write(self, key: str, data: bytes) -> None:
        target = self.path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def put(self, key: str, content_type: str, data: bytes) -> None:
        self.write(key, data)

    async def read(self, key: str, max_bytes: int) -> Optional[bytes]:
        target = self.path(key)
        if not target.is_file():
            return None
        if target.stat().st_size > max_bytes:
            raise ObjectTooLarge()
        return target.read_bytes()

    async def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)  # py3.8+

    async def aclose(self) -> None:
        return None
