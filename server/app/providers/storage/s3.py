"""S3-compatible adapter: SigV4 query-string presigning (path-style) + httpx for read/delete."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Sequence, Tuple
from urllib.parse import quote, urlsplit

import httpx

from app.config import Settings
from app.providers.storage import ObjectTooLarge, PresignedPut, StorageError

ALGORITHM = "AWS4-HMAC-SHA256"
HTTP_TIMEOUT = 20.0


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sign_query(
    method: str,
    host: str,
    path: str,
    headers: Dict[str, str],
    access_key: str,
    secret_key: str,
    region: str,
    now: datetime,
    expires_sec: int,
) -> str:
    """Canonical, signed query string of a presigned URL (AWS SigV4, service `s3`).

    `headers` (lowercase names) are signed together with `host`; the client must send them
    unchanged. `path` is the already-encoded absolute path.
    """
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    scope = "%s/%s/s3/aws4_request" % (day, region)
    signed = dict(headers, host=host)
    names = ";".join(sorted(signed))
    query = {
        "X-Amz-Algorithm": ALGORITHM,
        "X-Amz-Credential": "%s/%s" % (access_key, scope),
        "X-Amz-Date": stamp,
        "X-Amz-Expires": str(expires_sec),
        "X-Amz-SignedHeaders": names,
    }
    canonical_query = "&".join(
        "%s=%s" % (quote(k, safe=""), quote(v, safe="")) for k, v in sorted(query.items())
    )
    canonical_headers = "".join("%s:%s\n" % (k, signed[k].strip()) for k in sorted(signed))
    request = "\n".join(
        [method, path, canonical_query, canonical_headers, names, "UNSIGNED-PAYLOAD"]
    )
    to_sign = "\n".join([ALGORITHM, stamp, scope, hashlib.sha256(request.encode()).hexdigest()])
    k = _hmac(("AWS4" + secret_key).encode(), day)
    for part in (region, "s3", "aws4_request"):
        k = _hmac(k, part)
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    return "%s&X-Amz-Signature=%s" % (canonical_query, signature)


class S3Storage:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.bucket, self.region = bucket, region
        self.access_key, self.secret_key = access_key, secret_key
        self.host = urlsplit(self.endpoint).netloc
        self._client = client or httpx.AsyncClient(timeout=HTTP_TIMEOUT)

    @classmethod
    def from_settings(cls, s: Settings) -> Optional["S3Storage"]:
        if not (s.s3_endpoint and s.s3_bucket and s.s3_access_key):
            return None
        return cls(
            s.s3_endpoint, s.s3_bucket, s.s3_access_key, s.s3_secret_key.get_secret_value(),
            s.s3_region,
        )  # fmt: skip

    def _url(
        self,
        method: str,
        key: str,
        headers: Dict[str, str],
        expires_sec: int,
        now: Optional[datetime] = None,
    ) -> Tuple[str, datetime]:
        now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
        path = "/%s/%s" % (quote(self.bucket, safe=""), quote(key.lstrip("/"), safe="/"))
        query = sign_query(
            method, self.host, path, headers, self.access_key, self.secret_key, self.region,
            now, expires_sec,
        )  # fmt: skip
        return "%s%s?%s" % (self.endpoint, path, query), now + timedelta(seconds=expires_sec)

    def presign_put(
        self, key: str, content_type: str, size_bytes: int, expires_sec: int
    ) -> PresignedPut:
        # Both are signed: the bucket rejects a body of another length or type than declared.
        headers = {"content-length": str(size_bytes), "content-type": content_type}
        url, expires_at = self._url("PUT", key, headers, expires_sec)
        return PresignedPut(
            url=url, method="PUT", headers={"Content-Type": content_type}, expires_at=expires_at
        )

    async def put(self, key: str, content_type: str, data: bytes) -> None:
        """Server-side upload through a presigned PUT (the same signing the app clients use)."""
        signed = self.presign_put(key, content_type, len(data), 60)
        try:
            response = await self._client.put(signed.url, content=data, headers=signed.headers)
        except httpx.HTTPError as exc:
            raise StorageError("storage put failed") from exc
        if response.status_code not in (200, 201, 204):
            raise StorageError("storage put: HTTP %s" % response.status_code)

    async def read(self, key: str, max_bytes: int) -> Optional[bytes]:
        url, _ = self._url("GET", key, {}, 60)
        try:
            async with self._client.stream("GET", url) as response:
                if response.status_code == 404:
                    return None  # NoSuchKey; 403 is a credentials/clock problem, not "absent"
                if response.status_code != 200:
                    raise StorageError("storage read: HTTP %s" % response.status_code)
                declared = int(response.headers.get("content-length") or 0)
                if declared > max_bytes:
                    raise ObjectTooLarge()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise ObjectTooLarge()
                return bytes(body)
        except httpx.HTTPError as exc:
            raise StorageError("storage read failed") from exc

    async def delete(self, key: str) -> None:
        url, _ = self._url("DELETE", key, {}, 60)
        try:
            response = await self._client.delete(url)
        except httpx.HTTPError as exc:
            raise StorageError("storage delete failed") from exc
        if response.status_code not in (200, 204, 404):
            raise StorageError("storage delete: HTTP %s" % response.status_code)

    async def aclose(self) -> None:
        await self._client.aclose()


__all__: Sequence[str] = ("S3Storage", "sign_query")
