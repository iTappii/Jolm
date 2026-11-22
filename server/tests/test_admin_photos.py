"""Ш-55: the admin place form uploads a photo file into the object storage."""

import httpx
import pytest

from app.admin import api as admin_api
from app.db import fetch_all
from app.providers.storage import StorageError
from app.providers.storage.local import LocalStorage
from app.providers.storage.s3 import S3Storage
from tests.test_admin import add_place, logged_in

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def post_photo(client, place_id, csrf, content=JPEG, name="a.jpg"):
    return client.post(
        f"/admin/places/{place_id}/photos",
        data={"csrf_token": csrf},
        files={"photo": (name, content, "application/octet-stream")},
    )


@pytest.fixture
def local(monkeypatch, tmp_path):
    storage = LocalStorage(tmp_path, "http://test", "k" * 32)
    monkeypatch.setattr(admin_api, "make_storage", lambda: storage)
    return storage


async def test_upload_stores_the_file_and_adds_the_photo(client, conn, local):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    response = await post_photo(client, place_id, csrf)
    assert response.status_code == 303
    rows = await fetch_all(conn, "SELECT storage_key, source, status FROM place_photos")
    assert len(rows) == 1 and rows[0]["source"] == "team" and rows[0]["status"] == "approved"
    key = rows[0]["storage_key"]
    assert key.startswith("places/%s/" % place_id) and key.endswith(".jpg")
    assert await local.read(key, 1000) == JPEG  # the bytes really are in the storage
    page = await client.get(f"/admin/places/{place_id}")
    assert key in page.text and 'type="file"' in page.text and "multipart/form-data" in page.text

    png = await post_photo(client, place_id, csrf, PNG, "../../etc/passwd.png")
    assert png.status_code == 303  # the file name never reaches the key
    keys = [r["storage_key"] for r in await fetch_all(conn, "SELECT storage_key FROM place_photos")]
    assert len(keys) == 2 and all(".." not in k for k in keys)


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"", "пустой"), (b"GIF89a" + b"0" * 20, "JPEG, PNG или WebP"), (b"x" * 40, "JPEG")],
)
async def test_bad_files_are_refused(client, conn, local, content, message):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    response = await post_photo(client, place_id, csrf, content)
    assert response.status_code == 422 and message in response.text
    assert await fetch_all(conn, "SELECT id FROM place_photos") == []


async def test_oversized_file_is_refused(client, conn, local, monkeypatch):
    monkeypatch.setattr(admin_api, "MAX_UPLOAD_BYTES", 100)
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    response = await post_photo(client, place_id, csrf, JPEG + b"0" * 200)
    assert response.status_code == 422 and "больше" in response.text


async def test_no_storage_configured_says_so(client, conn, monkeypatch):
    monkeypatch.setattr(admin_api, "make_storage", lambda: None)
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    response = await post_photo(client, place_id, csrf)
    assert response.status_code == 422 and "STORAGE_PROVIDER" in response.text


async def test_upload_needs_csrf_and_login(client, conn, local):
    place_id = await add_place(conn, name_ru="Парк")
    anonymous = await post_photo(client, place_id, "x")
    assert anonymous.status_code in (302, 303, 401)
    await logged_in(client, conn)
    bad = await post_photo(client, place_id, "wrong-token")
    assert bad.status_code == 403
    assert await fetch_all(conn, "SELECT id FROM place_photos") == []


async def test_storage_failure_is_reported(client, conn, monkeypatch):
    class Broken:
        async def put(self, *args):
            raise StorageError("down")

    monkeypatch.setattr(admin_api, "make_storage", lambda: Broken())
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    response = await post_photo(client, place_id, csrf)
    assert response.status_code == 422 and "хранилище" in response.text.lower()
    assert await fetch_all(conn, "SELECT id FROM place_photos") == []


async def test_s3_put_sends_a_presigned_put_with_matching_length():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    storage = S3Storage(
        "http://127.0.0.1:9000", "jol-media", "key", "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )  # fmt: skip
    await storage.put("places/x/a.jpg", "image/jpeg", JPEG)
    request = seen[0]
    assert request.method == "PUT" and request.url.path == "/jol-media/places/x/a.jpg"
    assert request.content == JPEG and request.headers["content-type"] == "image/jpeg"
    assert request.headers["content-length"] == str(len(JPEG))
    assert "content-length%3Bcontent-type%3Bhost" in str(request.url)  # signed headers

    failing = S3Storage(
        "http://127.0.0.1:9000", "jol-media", "key", "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(403))),
    )  # fmt: skip
    with pytest.raises(StorageError):
        await failing.put("k.jpg", "image/jpeg", JPEG)


async def test_local_put_writes_the_file(tmp_path):
    storage = LocalStorage(tmp_path, "http://test", "k" * 32)
    await storage.put("places/a.jpg", "image/jpeg", JPEG)
    assert await storage.read("places/a.jpg", 1000) == JPEG
