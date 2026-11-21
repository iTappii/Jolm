"""Ш-44 (server): uploads, submissions, reviews list, account deletion of user content."""

from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.db import fetch_all, fetch_one
from app.main import create_app
from app.providers.storage.local import LocalStorage
from app.submissions import service
from tests.test_chat import sign_in
from tests.test_places import add_place

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 40
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 40


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    monkeypatch.setattr(get_settings(), "media_base_url", "https://media.example")


async def place(conn, name="Кафе"):
    return str(await add_place(conn, name, 76.95, 43.25))


async def upload(env, headers, data=PNG, content_type="image/png", declared=None, put=True):
    """Ask for an upload slot and PUT `data` to it; returns the slot answer."""
    size = len(data) if declared is None else declared
    response = await env.client.post(
        "/v1/uploads", headers=headers, json={"content_type": content_type, "size_bytes": size}
    )
    assert response.status_code == 201, response.text
    slot = response.json()
    if put:
        parts = urlsplit(slot["url"])
        sent = await env.client.put(
            "%s?%s" % (parts.path, parts.query), content=data, headers=slot["headers"]
        )
        assert sent.status_code == 200, sent.text
    return slot


async def submit(env, headers, type_, place_id, payload, **kw):
    return await env.client.post(
        "/v1/submissions",
        headers=headers,
        json={"type": type_, "place_id": place_id, "payload": payload},
        **kw,
    )


# --- uploads ---------------------------------------------------------------------------------


async def test_upload_needs_auth_and_storage(env, conn, monkeypatch):
    body = {"content_type": "image/png", "size_bytes": 10}
    assert (await env.client.post("/v1/uploads", json=body)).status_code == 401
    headers = await sign_in(conn)
    env.app.state.storage = None
    monkeypatch.setattr(get_settings(), "storage_provider", "")  # whatever .env says
    response = await env.client.post("/v1/uploads", headers=headers, json=body)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"


async def test_upload_slot_shape_and_limits(env, conn):
    headers = await sign_in(conn)
    slot = await upload(env, headers, put=False)
    assert set(slot) == {"upload_id", "url", "method", "headers", "expires_at", "max_bytes"}
    assert slot["method"] == "PUT" and slot["headers"] == {"Content-Type": "image/png"}
    assert slot["max_bytes"] == service.MAX_IMAGE_BYTES
    row = await fetch_one(conn, "SELECT storage_key, status FROM uploads")
    assert row["status"] == "pending"
    assert row["storage_key"].startswith("ugc/") and row["storage_key"].endswith(".png")
    assert str(slot["upload_id"]) not in row["storage_key"]  # nothing guessable or personal
    for bad in (
        {"content_type": "image/gif", "size_bytes": 10},
        {"content_type": "text/html", "size_bytes": 10},
        {"content_type": "image/png", "size_bytes": 0},
        {"content_type": "image/png", "size_bytes": service.MAX_IMAGE_BYTES + 1},
        {"content_type": "image/png"},
    ):
        response = await env.client.post("/v1/uploads", headers=headers, json=bad)
        assert response.status_code == 422, bad


async def test_upload_rate_limit(env, conn, monkeypatch):
    headers = await sign_in(conn)
    monkeypatch.setattr(service, "UPLOADS_PER_DAY", 2)
    for _ in range(2):
        await upload(env, headers, put=False)
    response = await env.client.post(
        "/v1/uploads", headers=headers, json={"content_type": "image/png", "size_bytes": 5}
    )
    assert response.status_code == 429 and response.headers["retry-after"]


async def test_dev_upload_endpoint_checks_signature_and_length(env, conn):
    headers = await sign_in(conn)
    slot = await upload(env, headers, put=False)
    parts = urlsplit(slot["url"])
    path = "%s?%s" % (parts.path, parts.query)
    wrong_len = await env.client.put(path, content=PNG + b"x", headers=slot["headers"])
    assert wrong_len.status_code == 422
    wrong_type = await env.client.put(path, content=PNG, headers={"Content-Type": "image/jpeg"})
    assert wrong_type.status_code == 403
    tampered = await env.client.put(
        path.replace("sig=", "sig=0"), content=PNG, headers=slot["headers"]
    )
    assert tampered.status_code == 403
    ok = await env.client.put(path, content=PNG, headers=slot["headers"])
    assert ok.status_code == 200


# --- submissions: shapes and validation -----------------------------------------------------


async def test_requires_auth_and_known_place(env, conn):
    pid = await place(conn)
    review = {"rating": 5}
    assert (await submit(env, {}, "review", pid, review)).status_code == 401
    assert (await env.client.get("/v1/me/submissions")).status_code == 401
    headers = await sign_in(conn)
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await submit(env, headers, "review", missing, review)).status_code == 404
    assert (await submit(env, headers, "review", None, review)).status_code == 422
    hidden = str(await add_place(conn, "Скрыто", 76.9, 43.2, status="hidden"))
    assert (await submit(env, headers, "review", hidden, review)).status_code == 404


async def test_each_type_is_accepted_and_published_pending_review(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    slot = await upload(env, headers, JPEG, "image/jpeg")
    cases = [
        ("review", pid, {"rating": 4, "text": "Очень вкусный плов и быстрое обслуживание"}),
        ("menu", pid, {"items": [{"name": "Плов", "price_kzt": 2500}, {"name": "Чай"}]}),
        ("photo", pid, {"upload_id": slot["upload_id"], "caption": "Вход"}),
        (
            "transit",
            None,
            {"route_ref": "92", "stop": "Абая", "interval_min": 12, "price_kzt": 100},
        ),
        ("transit", pid, {"route_ref": "Метро"}),
        ("price", pid, {"price_kzt": 1500, "audience": "child"}),
    ]
    for type_, place_id, payload in cases:
        response = await submit(env, headers, type_, place_id, payload)
        assert response.status_code == 201, (type_, response.text)
        body = response.json()
        assert response.headers["cache-control"] == "no-store"
        assert set(body) == {
            "id", "type", "place", "status", "pending_review", "reason_codes", "payload",
            "photo_url", "created_at", "decided_at",
        }  # fmt: skip
        assert body["type"] == type_ and body["status"] == "published_pending_review"
        assert body["pending_review"] is True and body["reason_codes"] == []
        assert (body["place"] is None) == (place_id is None)
    mine = (await env.client.get("/v1/me/submissions", headers=headers)).json()
    assert [i["type"] for i in mine["items"]] == [
        "price",
        "transit",
        "transit",
        "photo",
        "menu",
        "review",
    ]
    assert mine["next_cursor"] is None
    photo = mine["items"][3]
    assert photo["photo_url"].startswith("https://media.example/ugc/")
    assert "photo_key" not in photo["payload"] and photo["payload"]["caption"] == "Вход"
    assert mine["items"][0]["place"]["name"] == "Кафе"


@pytest.mark.parametrize(
    "type_, payload",
    [
        ("review", {"rating": 0}),
        ("review", {"rating": 6}),
        ("review", {"rating": "five"}),
        ("review", {"rating": 5, "text": "x" * 2001}),
        ("review", {"rating": 5, "extra": 1}),
        ("review", {}),
        ("menu", {}),
        ("menu", {"items": []}),
        ("menu", {"items": [{"name": "  "}]}),
        ("menu", {"items": [{"name": "Плов", "price_kzt": -1}]}),
        ("menu", {"items": [{"name": "Плов"}] * 101}),
        ("photo", {}),
        ("photo", {"upload_id": "not-a-uuid"}),
        ("transit", {"stop": "Абая"}),
        ("transit", {"route_ref": "92", "interval_min": 0}),
        ("transit", {"route_ref": "92", "price_kzt": -5}),
        ("price", {"price_kzt": 100, "audience": "vip"}),
        ("price", {"price_kzt": 10**9}),
        ("price", {}),
    ],
)
async def test_payload_validation(env, conn, type_, payload):
    pid = await place(conn)
    headers = await sign_in(conn)
    response = await submit(env, headers, type_, pid, payload)
    assert response.status_code == 422, response.text
    assert await fetch_all(conn, "SELECT id FROM submissions") == []


async def test_unknown_type_and_extra_top_level_field(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    assert (await submit(env, headers, "rumor", pid, {})).status_code == 422
    response = await env.client.post(
        "/v1/submissions",
        headers=headers,
        json={"type": "review", "place_id": pid, "payload": {"rating": 5}, "status": "approved"},
    )
    assert response.status_code == 422  # nobody can choose their own status


async def test_submission_limit_per_day(env, conn, monkeypatch):
    pid = await place(conn)
    headers = await sign_in(conn)
    monkeypatch.setattr(service, "SUBMISSIONS_PER_DAY", 2)
    for _ in range(2):
        assert (await submit(env, headers, "price", pid, {"price_kzt": 100})).status_code == 201
    assert (await submit(env, headers, "price", pid, {"price_kzt": 100})).status_code == 429


# --- photos ----------------------------------------------------------------------------------


async def test_photo_goes_to_place_with_url(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    slot = await upload(env, headers, WEBP, "image/webp")
    response = await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})
    assert response.status_code == 201, response.text
    key = (await fetch_one(conn, "SELECT storage_key FROM uploads"))["storage_key"]
    assert response.json()["photo_url"] == "https://media.example/" + key
    sub = await fetch_one(conn, "SELECT content_hash, place_photo_id FROM submissions")
    assert len(sub["content_hash"]) == 64 and sub["place_photo_id"] is not None
    assert (await fetch_one(conn, "SELECT status FROM uploads"))["status"] == "used"
    detail = (await env.client.get("/v1/places/%s" % pid)).json()
    assert [(p["storage_key"], p["url"], p["source"]) for p in detail["photos"]] == [
        (key, "https://media.example/" + key, "user")
    ]
    row = await fetch_one(conn, "SELECT author_user_id, status FROM place_photos")
    assert row["status"] == "approved" and row["author_user_id"] is not None


async def test_place_photo_url_is_null_without_media_base(env, conn, monkeypatch):
    monkeypatch.setattr(get_settings(), "media_base_url", "")
    pid = await place(conn)
    await conn.execute(
        "INSERT INTO place_photos (place_id, storage_key) VALUES (%s, 'a.jpg')", (pid,)
    )
    photos = (await env.client.get("/v1/places/%s" % pid)).json()["photos"]
    assert photos[0]["storage_key"] == "a.jpg" and photos[0]["url"] is None


@pytest.mark.parametrize(
    "data, declared",
    [
        (b"<html>not an image</html>" * 3, "image/jpeg"),  # content is not an image at all
        (PNG, "image/jpeg"),  # real image, wrong declared type
        (JPEG, "image/png"),
        (b"GIF89a" + b"\x00" * 40, "image/png"),
    ],
)
async def test_fake_images_are_rejected_and_queued_for_deletion(env, conn, data, declared):
    pid = await place(conn)
    headers = await sign_in(conn)
    slot = await upload(env, headers, data, declared)
    response = await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_image"
    # the rejection and the cleanup job are committed, not rolled back with the error
    assert (await fetch_one(conn, "SELECT status FROM uploads"))["status"] == "rejected"
    jobs = await fetch_all(conn, "SELECT kind, payload FROM jobs WHERE kind = 'storage.delete'")
    assert len(jobs) == 1 and len(jobs[0]["payload"]["keys"]) == 1
    assert await fetch_all(conn, "SELECT id FROM submissions") == []
    assert await fetch_all(conn, "SELECT id FROM place_photos") == []
    retry = await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})
    assert retry.status_code == 409  # a rejected slot is not reusable


async def test_upload_without_file_wrong_size_foreign_and_reuse(env, conn):
    pid = await place(conn)
    headers, other = await sign_in(conn), await sign_in(conn, "b@example.com")
    never_put = await upload(env, headers, put=False)
    r = await submit(env, headers, "photo", pid, {"upload_id": never_put["upload_id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "upload_not_found"
    short = await upload(env, headers, PNG, declared=len(PNG) + 5, put=False)  # PUT is checked
    key = (
        await fetch_one(
            conn, "SELECT storage_key FROM uploads WHERE id = %s", (short["upload_id"],)
        )
    )["storage_key"]
    env.storage.write(key, PNG)  # stored object differs from the declared size
    r = await submit(env, headers, "photo", pid, {"upload_id": short["upload_id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_image"
    mine = await upload(env, headers)
    r = await submit(env, other, "photo", pid, {"upload_id": mine["upload_id"]})
    assert r.status_code == 422  # somebody else's slot
    assert (
        await submit(env, headers, "photo", pid, {"upload_id": mine["upload_id"]})
    ).status_code == 201
    again = await submit(env, headers, "photo", pid, {"upload_id": mine["upload_id"]})
    assert again.status_code == 409 and again.json()["error"]["code"] == "upload_used"
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await submit(env, headers, "photo", pid, {"upload_id": unknown})).status_code == 422


async def test_expired_slot_and_missing_storage(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    slot = await upload(env, headers)
    await conn.execute("UPDATE uploads SET expires_at = now() - interval '1 second'")
    r = await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "upload_not_found"


async def test_menu_with_photo_only(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    slot = await upload(env, headers, JPEG, "image/jpeg")
    r = await submit(env, headers, "menu", pid, {"upload_id": slot["upload_id"]})
    assert r.status_code == 201 and r.json()["photo_url"]
    assert (
        await fetch_all(conn, "SELECT id FROM place_photos") == []
    )  # a menu photo is not a place photo


# --- reviews ----------------------------------------------------------------------------------


async def test_reviews_list_summary_and_pagination(env, conn):
    pid = await place(conn)
    other = await place(conn, "Другое")
    for i, rating in enumerate([5, 4, 2]):
        headers = await sign_in(conn, "u%d@example.com" % i)
        r = await submit(
            env, headers, "review", pid, {"rating": rating, "text": "Отзыв номер %d, подробный" % i}
        )
        assert r.status_code == 201
    headers = await sign_in(conn, "u9@example.com")
    await submit(env, headers, "review", other, {"rating": 1})
    await submit(env, headers, "price", pid, {"price_kzt": 100})  # not a review
    await conn.execute(
        "UPDATE submissions SET created_at = now() -"
        " make_interval(mins => 10 - (payload->>'rating')::int) WHERE type = 'review'"
    )

    response = await env.client.get("/v1/places/%s/reviews" % pid)  # public
    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {"count": 3, "average": 3.7}
    assert [i["rating"] for i in body["items"]] == [5, 4, 2]  # newest first
    first = body["items"][0]
    assert set(first) == {"id", "rating", "text", "author_name", "created_at", "pending_review"}
    assert first["pending_review"] is True and first["author_name"] is None

    page1 = (await env.client.get("/v1/places/%s/reviews?limit=2" % pid)).json()
    assert [i["rating"] for i in page1["items"]] == [5, 4] and page1["next_cursor"]
    page2 = (
        await env.client.get(
            "/v1/places/%s/reviews" % pid, params={"limit": 2, "cursor": page1["next_cursor"]}
        )
    ).json()
    assert [i["rating"] for i in page2["items"]] == [2] and page2["next_cursor"] is None
    assert page2["summary"]["count"] == 3
    bad = await env.client.get("/v1/places/%s/reviews?cursor=garbage" % pid)
    assert bad.status_code == 422
    assert (await env.client.get("/v1/places/%s/reviews?limit=0" % pid)).status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await env.client.get("/v1/places/%s/reviews" % unknown)).status_code == 404


async def test_reviews_show_only_published_and_approved(env, conn):
    pid = await place(conn)
    for status in (
        "published_pending_review",
        "approved",
        "rejected",
        "rejected_auto",
        "pending_filter",
    ):
        headers = await sign_in(conn, "%s@example.com" % status)
        sub = (await submit(env, headers, "review", pid, {"rating": 5})).json()
        await conn.execute("UPDATE submissions SET status = %s WHERE id = %s", (status, sub["id"]))
    items = (await env.client.get("/v1/places/%s/reviews" % pid)).json()["items"]
    assert sorted(i["pending_review"] for i in items) == [False, True]


async def test_one_review_per_user_and_place(env, conn):
    pid, other = await place(conn), await place(conn, "Другое")
    headers = await sign_in(conn)
    assert (await submit(env, headers, "review", pid, {"rating": 5})).status_code == 201
    again = await submit(env, headers, "review", pid, {"rating": 1})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_submitted"
    assert (await submit(env, headers, "review", other, {"rating": 1})).status_code == 201
    await conn.execute("UPDATE submissions SET status = 'rejected' WHERE place_id = %s", (pid,))
    assert (
        await submit(env, headers, "review", pid, {"rating": 3})
    ).status_code == 201  # may retry


async def test_my_submissions_are_private_and_paged(env, conn):
    pid = await place(conn)
    mine, theirs = await sign_in(conn), await sign_in(conn, "b@example.com")
    for _ in range(3):
        await submit(env, mine, "price", pid, {"price_kzt": 100})
    await submit(env, theirs, "price", pid, {"price_kzt": 200})
    first = (await env.client.get("/v1/me/submissions?limit=2", headers=mine)).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = (
        await env.client.get(
            "/v1/me/submissions", params={"limit": 2, "cursor": first["next_cursor"]}, headers=mine
        )
    ).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    ids = {i["id"] for i in first["items"] + rest["items"]}
    assert len(ids) == 3 and all(
        i["payload"]["price_kzt"] == 100 for i in first["items"] + rest["items"]
    )


# --- account deletion --------------------------------------------------------------------------


async def test_account_deletion_anonymizes_published_and_removes_the_rest(env, conn):
    pid = await place(conn)
    other = await place(conn, "Другое")
    headers = await sign_in(conn, "leaver@example.com")
    keeper = await sign_in(conn, "stays@example.com")
    published = await submit(
        env, headers, "review", pid, {"rating": 5, "text": "Отличное место для ужина"}
    )
    photo_slot = await upload(env, headers)
    assert (
        await submit(env, headers, "photo", pid, {"upload_id": photo_slot["upload_id"]})
    ).status_code == 201
    await upload(env, headers, put=False)  # an unused slot
    await submit(env, headers, "review", other, {"rating": 2})
    await submit(env, keeper, "review", pid, {"rating": 3})
    await conn.execute(
        "UPDATE submissions SET status = 'rejected' WHERE place_id = %s AND user_id IS NOT NULL"
        " AND type = 'review' AND (payload->>'rating') = '2'",
        (other,),
    )
    photo_key = (
        await fetch_one(
            conn, "SELECT payload->>'photo_key' AS k FROM submissions WHERE type = 'photo'"
        )
    )["k"]

    assert (await env.client.delete("/v1/me", headers=headers)).status_code == 204

    rows = await fetch_all(
        conn, "SELECT type, user_id, status FROM submissions ORDER BY type, user_id IS NOT NULL"
    )
    kept = [(r["type"], r["status"], r["user_id"] is None) for r in rows]
    assert kept == [
        ("photo", "published_pending_review", True),
        ("review", "published_pending_review", True),
        ("review", "published_pending_review", False),
    ]
    assert (
        await fetch_all(conn, "SELECT id FROM uploads") == []
    )  # slots are gone (all were this user's)
    assert (await fetch_one(conn, "SELECT author_user_id FROM place_photos"))[
        "author_user_id"
    ] is None
    jobs = await fetch_all(conn, "SELECT payload FROM jobs WHERE kind = 'storage.delete'")
    keys = [k for j in jobs for k in j["payload"]["keys"]]
    assert len(keys) == 1 and photo_key not in keys  # the published photo stays in the bucket
    reviews = (await env.client.get("/v1/places/%s/reviews" % pid)).json()["items"]
    assert len(reviews) == 2 and all(r["author_name"] is None for r in reviews)
    assert published.json()["id"] in {r["id"] for r in reviews}  # the text outlives the account


async def test_local_media_is_served_in_dev(conn, tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    settings = get_settings()
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "storage_local_dir", str(tmp_path))
    monkeypatch.setattr(settings, "app_env", "test")
    (tmp_path / "ugc").mkdir()
    (tmp_path / "ugc" / "a.png").write_bytes(PNG)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/media/ugc/a.png")).content == PNG
        assert (await client.get("/media/ugc/missing.png")).status_code == 404


async def test_storage_delete_job_removes_objects(tmp_path, monkeypatch):
    from app import worker
    from app.providers import storage as storage_module

    local = LocalStorage(tmp_path, "http://test", "k" * 32)
    local.write("ugc/a.png", PNG)
    monkeypatch.setattr(storage_module, "make_storage", lambda settings=None: local)
    handler = worker._HANDLERS["storage.delete"]
    await handler(None, {"keys": ["ugc/a.png", "ugc/never-existed.png"]})
    assert await local.read("ugc/a.png", 100) is None
    monkeypatch.setattr(storage_module, "make_storage", lambda settings=None: None)
    await handler(None, {"keys": ["ugc/a.png"]})  # no storage configured: logged, not fatal


# --- retention cleanup (worker job) ------------------------------------------------------------


async def test_retention_cleanup_drops_stale_slots_and_old_retired_tokens(conn):
    from app import worker
    from app.auth import sessions

    first = await sessions.sign_in(conn, "email", "clean@example.org", "en")
    user = await fetch_one(conn, "SELECT id FROM users")
    session = await fetch_one(conn, "SELECT id FROM sessions")
    for key, status, expires in [
        ("ugc/old-pending.png", "pending", "-1 hour"),
        ("ugc/old-rejected.png", "rejected", "-2 hours"),
        ("ugc/old-used.png", "used", "-1 day"),  # attached to a submission: kept
        ("ugc/live-pending.png", "pending", "+30 minutes"),
    ]:
        await conn.execute(
            "INSERT INTO uploads (user_id, storage_key, content_type, size_bytes, status,"
            " expires_at) VALUES (%s, %s, 'image/png', 10, %s, now() + %s::interval)",
            (user["id"], key, status, expires),
        )
    for name, age in [("old", "61 days"), ("recent", "1 day")]:
        await conn.execute(
            "INSERT INTO session_retired_tokens (token_hash, session_id, retired_at)"
            " VALUES (%s, %s, now() - %s::interval)",
            (name, session["id"], age),
        )
    assert first.refresh_token

    await worker._retention_cleanup(conn, {})

    left = [r["storage_key"] for r in await fetch_all(conn, "SELECT storage_key FROM uploads")]
    assert sorted(left) == ["ugc/live-pending.png", "ugc/old-used.png"]
    rows = await fetch_all(conn, "SELECT token_hash FROM session_retired_tokens")
    tokens = [r["token_hash"] for r in rows]
    assert tokens == ["recent"]
    job = await fetch_one(conn, "SELECT payload FROM jobs WHERE kind = 'storage.delete'")
    assert sorted(job["payload"]["keys"]) == ["ugc/old-pending.png", "ugc/old-rejected.png"]
    await worker._retention_cleanup(conn, {})  # idempotent: nothing new to delete
    count = await fetch_one(conn, "SELECT count(*) AS n FROM jobs WHERE kind = 'storage.delete'")
    assert count["n"] == 1
    assert any(s.kind == "retention.cleanup" for s in worker.SCHEDULES)
