"""Ш-44: storage adapters (S3 SigV4 presigning, local adapter) and the media URL helper."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.providers.storage import ObjectTooLarge, StorageError, make_storage, media_url
from app.providers.storage.local import LocalStorage
from app.providers.storage.s3 import S3Storage, sign_query


def test_sigv4_matches_the_aws_documented_presign_example():
    """GET https://examplebucket.s3.amazonaws.com/test.txt, from the AWS SigV4 query-auth docs."""
    query = sign_query(
        "GET",
        "examplebucket.s3.amazonaws.com",
        "/test.txt",
        {},
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        datetime(2013, 5, 24, tzinfo=timezone.utc),
        86400,
    )
    assert query.endswith(
        "X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"
    )


def s3(client=None):
    return S3Storage("http://127.0.0.1:9000", "jol", "AKID", "secret", client=client)


def test_s3_presigned_put_signs_length_and_type():
    put = s3().presign_put("ugc/2026/11/a b.jpg", "image/jpeg", 1234, 900)
    parts = urlsplit(put.url)
    assert (parts.netloc, parts.path) == ("127.0.0.1:9000", "/jol/ugc/2026/11/a%20b.jpg")
    query = parse_qs(parts.query)
    assert query["X-Amz-SignedHeaders"] == ["content-length;content-type;host"]
    assert query["X-Amz-Expires"] == ["900"] and len(query["X-Amz-Signature"][0]) == 64
    assert put.method == "PUT" and put.headers == {"Content-Type": "image/jpeg"}
    other = s3().presign_put("ugc/2026/11/a b.jpg", "image/jpeg", 1235, 900)
    assert parse_qs(urlsplit(other.url).query)["X-Amz-Signature"] != query["X-Amz-Signature"]


async def test_s3_read_and_delete_over_http():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.url.path.endswith("missing.jpg"):
            return httpx.Response(404)
        if request.url.path.endswith("big.jpg"):
            return httpx.Response(200, content=b"x" * 100)
        if request.url.path.endswith("broken.jpg"):
            return httpx.Response(403)
        return httpx.Response(204 if request.method == "DELETE" else 200, content=b"abc")

    storage = s3(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await storage.read("ugc/ok.jpg", 10) == b"abc"
    assert await storage.read("ugc/missing.jpg", 10) is None
    with pytest.raises(ObjectTooLarge):
        await storage.read("ugc/big.jpg", 10)
    with pytest.raises(StorageError):
        await storage.read("ugc/broken.jpg", 10)  # a credentials problem is not "absent"
    await storage.delete("ugc/ok.jpg")
    await storage.delete("ugc/missing.jpg")  # a missing object is fine
    assert ("DELETE", "/jol/ugc/ok.jpg") in seen
    await storage.aclose()


def test_make_storage_by_settings(tmp_path):
    base = dict(app_env="test", _env_file=None)
    assert make_storage(Settings(**base)) is None
    assert make_storage(Settings(storage_provider="s3", **base)) is None  # not configured
    configured = Settings(
        storage_provider="s3", s3_endpoint="http://x:9000", s3_bucket="b", s3_access_key="k",
        s3_secret_key=SecretStr("s"), **base,
    )  # fmt: skip
    assert isinstance(make_storage(configured), S3Storage)
    local = Settings(storage_provider="local", storage_local_dir=str(tmp_path), **base)
    assert isinstance(make_storage(local), LocalStorage)
    prod = Settings(storage_provider="local", storage_local_dir=str(tmp_path), app_env="prod")
    assert make_storage(prod) is None  # the local adapter never runs outside dev/test


def test_media_url():
    assert media_url("ugc/a.jpg", "https://m.example/") == "https://m.example/ugc/a.jpg"
    assert media_url("/ugc/a.jpg", "https://m.example") == "https://m.example/ugc/a.jpg"
    assert media_url("ugc/a.jpg", "") is None and media_url(None, "https://m.example") is None


async def test_local_storage_roundtrip_and_traversal(tmp_path):
    storage = LocalStorage(tmp_path, "http://x", "k" * 32)
    storage.write("ugc/a.png", b"123")
    assert await storage.read("ugc/a.png", 10) == b"123"
    with pytest.raises(ObjectTooLarge):
        await storage.read("ugc/a.png", 2)
    await storage.delete("ugc/a.png")
    await storage.delete("ugc/a.png")
    assert await storage.read("ugc/a.png", 10) is None
    with pytest.raises(ValueError):
        storage.path("../outside")
    put = storage.presign_put("ugc/a.png", "image/png", 3, 60)
    query = parse_qs(urlsplit(put.url).query)
    args = ("ugc/a.png", "image/png", 3, int(query["exp"][0]), query["sig"][0])
    assert storage.verify(*args)
    assert not storage.verify("ugc/b.png", *args[1:])
    assert not storage.verify("ugc/a.png", "image/jpeg", *args[2:])
    assert not storage.verify(*args[:3], args[3] - 1000, args[4])
