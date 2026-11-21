"""Ш-45: auto-filter rules (pure ones directly, database ones through the API) and moderation."""

import pytest

from app.db import fetch_all, fetch_one
from app.submissions import autofilter
from tests.test_admin import logged_in
from tests.test_chat import sign_in
from tests.test_submissions import JPEG, PNG, place, secret, submit, upload  # noqa: F401


@pytest.mark.parametrize(
    "text, codes",
    [
        ("Хороший кофе и приятная атмосфера", []),
        ("Great views of the mountains, would go again", []),
        ("Керемет жер, ұнады, міндетті түрде барыңыз", []),
        ("!!!!!!!!!!!!", ["no_letters", "repeated_text"]),
        ("1234567890", ["no_letters", "contains_contact"]),
        ("ааааааааааа хорошо", ["repeated_text"]),
        ("вкусно вкусно вкусно вкусно вкусно круто", ["repeated_text"]),
        ("Заходите на https://spam.example/promo", ["contains_link"]),
        ("пишите на www.cheap-tours.com", ["contains_link"]),
        ("Лучшие цены t.me/best_deals", ["contains_link"]),
        ("пишите cheap@tours.kz сейчас", ["contains_link"]),
        ("tickets on promo-tours.kz today", ["contains_link"]),
        ("Звоните +7 701 123 45 67 скидки", ["contains_contact"]),
        ("звоните 87011234567", ["contains_contact"]),
        ("этот официант хуйня полная", ["profanity"]),
        ("ХУУУЙНЯ а не кафе", ["profanity"]),
        ("what the fuck was that", ["profanity"]),
        ("this place is shitty", ["profanity"]),
        ("сіктір бол мына жерден", ["profanity"]),
        # innocent words that merely look similar must pass
        ("Скучать не пришлось, оскорбительного ничего, хлеб и херсонская вишня", []),
        ("Классная ассамблея, дикий восторг, шитьё и гастрономия", []),
        ("Тел. в зале 12 столов, 3 этажа, рейтинг 4.5 из 5", []),
    ],
)
def test_text_rules(text, codes):
    got = autofilter.text_reasons(text, need_letters=True)
    assert sorted(got) == sorted(codes), (text, got)


def test_collapse_and_profanity_list_loads():
    assert autofilter.collapse("Хууууй") == "хуй" and autofilter.collapse("ёжик") == "ежик"
    prefixes, exact = autofilter.profanity_lists()
    assert len(prefixes) > 20 and "сука" in exact


@pytest.mark.parametrize(
    "type_, payload, known, bad",
    [
        ("price", {"price_kzt": 2000}, None, False),
        ("price", {"price_kzt": 0}, 2000, False),  # a free day
        ("price", {"price_kzt": 250_000}, None, True),
        ("price", {"price_kzt": 25_000}, 2000, True),  # 12x the known price
        ("price", {"price_kzt": 100, "audience": "adult"}, 2000, True),  # 20x too cheap
        ("price", {"price_kzt": 100, "audience": "child"}, 2000, False),  # a child ticket may be
        ("menu", {"items": [{"name": "Плов", "price_kzt": 2500}, {"name": "Чай"}]}, None, False),
        ("menu", {"items": [{"name": "Плов", "price_kzt": 5}]}, None, True),
        ("menu", {"items": [{"name": "Плов", "price_kzt": 900_000}]}, None, True),
        ("transit", {"route_ref": "92", "price_kzt": 100}, None, False),
        ("transit", {"route_ref": "92", "price_kzt": 90_000}, None, True),
        ("transit", {"route_ref": "92"}, None, False),
    ],
)
def test_price_plausibility(type_, payload, known, bad):
    assert (autofilter.price_reasons(type_, payload, known) != []) is bad


# --- through the API ----------------------------------------------------------------------------


async def test_review_garbage_is_rejected_auto_with_reasons(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    for text in ("ok", "купите тут https://x.example", "блядь какой ужас тут"):
        r = await submit(env, headers, "review", pid, {"rating": 1, "text": text})
        assert r.status_code == 201, r.text  # received, but not published
        body = r.json()
        assert body["status"] == "rejected_auto" and body["pending_review"] is False
        assert body["reason_codes"]
    assert (await env.client.get("/v1/places/%s/reviews" % pid)).json()["items"] == []
    row = await fetch_one(conn, "SELECT filter_result FROM submissions ORDER BY created_at LIMIT 1")
    assert row["filter_result"] == {"passed": False, "reasons": ["too_short"], "version": 1}
    # a rejected review does not block a real one
    ok = await submit(env, headers, "review", pid, {"rating": 4, "text": "Приятное место, вкусно"})
    assert ok.json()["status"] == "published_pending_review"


async def test_rating_only_review_passes(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    r = await submit(env, headers, "review", pid, {"rating": 5})
    assert r.json()["status"] == "published_pending_review"


async def test_duplicate_review_text(env, conn):
    pid, other = await place(conn), await place(conn, "Другое")
    first, second = await sign_in(conn), await sign_in(conn, "b@example.com")
    text = "Отличное место, всем рекомендую"
    assert (await submit(env, first, "review", pid, {"rating": 5, "text": text})).status_code == 201
    same_place = await submit(env, second, "review", pid, {"rating": 5, "text": text.upper()})
    assert same_place.json()["reason_codes"] == ["duplicate_text"]  # another person, same place
    same_user = await submit(env, first, "review", other, {"rating": 5, "text": text})
    assert same_user.json()["reason_codes"] == ["duplicate_text"]  # one person copying elsewhere
    fresh = await submit(env, second, "review", other, {"rating": 5, "text": text})
    assert fresh.json()["status"] == "published_pending_review"  # other person, other place


async def test_duplicate_photo_by_hash(env, conn):
    pid = await place(conn)
    first, second = await sign_in(conn), await sign_in(conn, "b@example.com")
    one = await upload(env, first, PNG)
    assert (
        await submit(env, first, "photo", pid, {"upload_id": one["upload_id"]})
    ).status_code == 201
    two = await upload(env, second, PNG)  # the very same bytes
    dup = await submit(env, second, "photo", pid, {"upload_id": two["upload_id"]})
    assert dup.status_code == 201 and dup.json()["reason_codes"] == ["duplicate_photo"]
    assert dup.json()["photo_url"] is None
    assert len(await fetch_all(conn, "SELECT id FROM place_photos")) == 1  # nothing published
    jobs = await fetch_all(conn, "SELECT payload FROM jobs WHERE kind = 'storage.delete'")
    assert len(jobs) == 1  # the duplicate's file is queued for deletion
    other_image = await upload(env, second, JPEG, "image/jpeg")
    fine = await submit(env, second, "photo", pid, {"upload_id": other_image["upload_id"]})
    assert fine.json()["status"] == "published_pending_review"


async def test_moderator_rejected_photo_cannot_come_back(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    slot = await upload(env, headers, PNG)
    sub = (await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})).json()
    await conn.execute("UPDATE submissions SET status = 'rejected' WHERE id = %s", (sub["id"],))
    again = await upload(env, headers, PNG)
    r = await submit(env, headers, "photo", pid, {"upload_id": again["upload_id"]})
    assert r.json()["reason_codes"] == ["rejected_photo"]


async def test_price_against_the_known_entry_price(env, conn):
    pid = await place(conn)
    await conn.execute("UPDATE places SET entry_price_kzt = 2000 WHERE id = %s", (pid,))
    headers = await sign_in(conn)
    bad = await submit(env, headers, "price", pid, {"price_kzt": 50_000})
    assert bad.json()["reason_codes"] == ["implausible_price"]
    good = await submit(env, headers, "price", pid, {"price_kzt": 2500})
    assert good.json()["status"] == "published_pending_review"


async def test_menu_and_transit_text_are_filtered_too(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    menu = await submit(env, headers, "menu", pid, {"items": [{"name": "Плов http://x.example"}]})
    assert menu.json()["reason_codes"] == ["contains_link"]
    transit = await submit(env, headers, "transit", None, {"route_ref": "92", "note": "fuck this"})
    assert transit.json()["reason_codes"] == ["profanity"]
    caption = await upload(env, headers, PNG)
    photo = await submit(
        env,
        headers,
        "photo",
        pid,
        {"upload_id": caption["upload_id"], "caption": "звоните 87011234567"},
    )
    assert photo.json()["reason_codes"] == ["contains_contact"]


# --- moderation in the admin -------------------------------------------------------------------


async def pending_ids(conn):
    rows = await fetch_all(conn, "SELECT id, type FROM submissions ORDER BY created_at")
    return {r["type"]: str(r["id"]) for r in rows}


async def test_moderation_requires_admin_and_csrf(env, conn):
    anon = await env.client.get("/admin/moderation")
    assert anon.status_code == 303 and anon.headers["location"] == "/admin/login"
    pid = await place(conn)
    headers = await sign_in(conn)
    sub = (await submit(env, headers, "review", pid, {"rating": 5})).json()
    url = "/admin/moderation/%s/approve" % sub["id"]
    assert (await env.client.post(url, data={})).status_code == 303  # not logged in
    csrf = await logged_in(env.client, conn)
    forged = await env.client.post(url, data={"csrf_token": "nope"})
    assert forged.status_code == 403
    assert (await fetch_one(conn, "SELECT status FROM submissions"))[
        "status"
    ] == "published_pending_review"
    assert (
        await env.client.post("/admin/moderation/%s/maybe" % sub["id"], data={"csrf_token": csrf})
    ).status_code == 404
    assert (
        await env.client.post("/admin/moderation/not-a-uuid/approve", data={"csrf_token": csrf})
    ).status_code == 404


async def test_queue_page_shows_only_published_pending(env, conn):
    pid = await place(conn, "Кофейня Тест")
    headers = await sign_in(conn)
    await submit(env, headers, "review", pid, {"rating": 4, "text": "Уютное место, вкусный кофе"})
    await submit(
        env, headers, "review", pid, {"rating": 1, "text": "x"}
    )  # rejected_auto: not queued
    await submit(env, headers, "price", pid, {"price_kzt": 1500, "note": "<b>взрослый</b>"})
    await logged_in(env.client, conn)
    page = await env.client.get("/admin/moderation")
    assert page.status_code == 200
    assert "Уютное место, вкусный кофе" in page.text and "Кофейня Тест" in page.text
    assert "В очереди: 2" in page.text
    assert "<b>взрослый</b>" not in page.text and "&lt;b&gt;" in page.text  # escaped


async def test_approve_and_reject_flow(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    review = (
        await submit(env, headers, "review", pid, {"rating": 5, "text": "Прекрасное место"})
    ).json()
    slot = await upload(env, headers, PNG)
    photo = (await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})).json()
    csrf = await logged_in(env.client, conn)
    admin_id = (await fetch_one(conn, "SELECT id FROM admins"))["id"]

    approve = await env.client.post(
        "/admin/moderation/%s/approve" % review["id"], data={"csrf_token": csrf}
    )
    assert (
        approve.status_code == 303
        and approve.headers["location"] == "/admin/moderation?done=approve"
    )
    row = await fetch_one(
        conn,
        "SELECT status, moderator_id, decided_at FROM submissions WHERE id = %s",
        (review["id"],),
    )
    assert row["status"] == "approved" and row["moderator_id"] == admin_id and row["decided_at"]
    items = (await env.client.get("/v1/places/%s/reviews" % pid)).json()["items"]
    assert [i["pending_review"] for i in items] == [False]  # the "checked later" mark is gone

    again = await env.client.post(
        "/admin/moderation/%s/reject" % review["id"], data={"csrf_token": csrf}
    )
    assert again.headers["location"] == "/admin/moderation?done=already"  # decided once only
    assert (await fetch_one(conn, "SELECT status FROM submissions WHERE id = %s", (review["id"],)))[
        "status"
    ] == "approved"

    reject = await env.client.post(
        "/admin/moderation/%s/reject" % photo["id"], data={"csrf_token": csrf}
    )
    assert reject.headers["location"] == "/admin/moderation?done=reject"
    assert (await fetch_one(conn, "SELECT status FROM place_photos"))["status"] == "rejected"
    assert (await env.client.get("/v1/places/%s" % pid)).json()["photos"] == []
    jobs = await fetch_all(conn, "SELECT payload FROM jobs WHERE kind = 'storage.delete'")
    assert len(jobs) == 1 and len(jobs[0]["payload"]["keys"]) == 1
    page = await env.client.get("/admin/moderation")
    assert "Очередь пуста" in page.text


async def test_rejected_review_disappears(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    sub = (
        await submit(env, headers, "review", pid, {"rating": 2, "text": "Не понравилось совсем"})
    ).json()
    csrf = await logged_in(env.client, conn)
    await env.client.post("/admin/moderation/%s/reject" % sub["id"], data={"csrf_token": csrf})
    assert (await env.client.get("/v1/places/%s/reviews" % pid)).json()["summary"] == {
        "count": 0,
        "average": None,
    }
    mine = (await env.client.get("/v1/me/submissions", headers=headers)).json()["items"]
    assert mine[0]["status"] == "rejected" and mine[0]["pending_review"] is False


async def test_approving_menu_and_price_applies_them_to_the_place(env, conn):
    pid = await place(conn)
    await conn.execute("UPDATE places SET entry_price_kzt = 1000 WHERE id = %s", (pid,))
    headers = await sign_in(conn)
    menu = (
        await submit(env, headers, "menu", pid, {"items": [{"name": "Плов", "price_kzt": 2500}]})
    ).json()
    adult = (await submit(env, headers, "price", pid, {"price_kzt": 1500})).json()
    child = (
        await submit(env, headers, "price", pid, {"price_kzt": 500, "audience": "child"})
    ).json()
    transit = (await submit(env, headers, "transit", None, {"route_ref": "92"})).json()
    # not applied while waiting
    detail = (await env.client.get("/v1/places/%s" % pid)).json()
    assert detail["menu"] is None and detail["prices"]["entry_price_kzt"] == 1000
    csrf = await logged_in(env.client, conn)
    for sub in (menu, adult, child, transit):
        r = await env.client.post(
            "/admin/moderation/%s/approve" % sub["id"], data={"csrf_token": csrf}
        )
        assert r.status_code == 303
    detail = (await env.client.get("/v1/places/%s" % pid)).json()
    assert detail["menu"]["payload"] == {"items": [{"name": "Плов", "price_kzt": 2500}]}
    assert detail["menu"]["source"] == "user"
    assert detail["prices"]["entry_price_kzt"] == 1500  # the child ticket did not touch it
    row = await fetch_one(conn, "SELECT manual_override FROM places WHERE id = %s", (pid,))
    assert row["manual_override"] == ["entry_price_kzt"]  # the importer will not overwrite it
    statuses = {r["status"] for r in await fetch_all(conn, "SELECT status FROM submissions")}
    assert statuses == {"approved"}


async def test_deleted_admin_keeps_the_decision(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    sub = (await submit(env, headers, "review", pid, {"rating": 3})).json()
    csrf = await logged_in(env.client, conn)
    await env.client.post("/admin/moderation/%s/approve" % sub["id"], data={"csrf_token": csrf})
    await conn.execute("DELETE FROM admins")
    row = await fetch_one(conn, "SELECT status, moderator_id FROM submissions")
    assert row == {"status": "approved", "moderator_id": None}
