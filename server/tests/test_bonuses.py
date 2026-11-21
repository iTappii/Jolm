"""Ш-46: bonus ledger, accrual after approval, the temporary formula, admin constants."""

import psycopg.errors
import pytest

from app.db import fetch_all, fetch_one
from app.submissions import bonus_policy
from tests.test_admin import logged_in
from tests.test_chat import sign_in
from tests.test_submissions import PNG, place, secret, submit, upload  # noqa: F401

C = bonus_policy.resolve({})  # the defaults of the temporary formula


# --- the formula (pure) -----------------------------------------------------------------------


def test_defaults_match_the_migration_seed():
    assert set(C) == set(bonus_policy.DEFAULTS)


def test_formula_age_and_frequency():
    # nothing known about the field and a place in 20+ trips: the data is needed most
    assert bonus_policy.compute("menu", C, None, 50).amount == 100 * 2 * 2
    # a fresh field and a place nobody plans to visit: the least
    assert bonus_policy.compute("menu", C, 0, 0).amount == round(100 * 0.5 * 1)
    # linear in between: half of the full age and half of the full trips
    half = bonus_policy.compute("menu", C, 90, 10)
    assert half.age_factor == pytest.approx(1.25) and half.freq_factor == pytest.approx(1.5)
    assert half.amount == round(100 * 1.25 * 1.5)
    # older than "full" does not grow further
    assert bonus_policy.compute("menu", C, 9999, 0).age_factor == 2
    # transit data is not about a place: no factors
    t = bonus_policy.compute("transit", C, None, 99)
    assert (t.age_factor, t.freq_factor, t.amount) == (1, 1, 60)


def test_zero_base_pays_nothing_and_tiny_amounts_round_up_to_one():
    assert bonus_policy.compute("review", {**C, "base_review": 0}, None, 0).amount == 0
    assert bonus_policy.compute("review", {**C, "base_review": 0.2}, 0, 0).amount == 1
    huge = {**C, "base_menu": 10_000, "age_max": 10, "freq_max": 10}
    assert bonus_policy.compute("menu", huge, None, 10**6).amount == bonus_policy.MAX_BONUS


def test_validate_form():
    form = {k: "%g" % v for k, v in C.items()}
    values, errors = bonus_policy.validate(form)
    assert not errors and values["age_min"] == 0.5
    values, errors = bonus_policy.validate(
        {**form, "base_menu": "abc", "age_min": "3", "age_max": "1"}
    )
    assert set(errors) == {"base_menu", "age_min"}
    assert bonus_policy.validate({**form, "freq_min": "-1"})[1].keys() == {"freq_min"}
    assert bonus_policy.validate({k: v for k, v in form.items() if k != "base_menu"})[1]


# --- accrual ----------------------------------------------------------------------------------


async def approve(env, conn, csrf, sub_id):
    r = await env.client.post("/admin/moderation/%s/approve" % sub_id, data={"csrf_token": csrf})
    assert r.status_code == 303, r.text
    return r


async def ledger(conn):
    return await fetch_all(conn, "SELECT * FROM bonus_ledger ORDER BY created_at")


async def add_trips(conn, user_id, place_id, n):
    for _ in range(n):
        trip = await fetch_one(
            conn,
            "INSERT INTO trips (user_id, brief, start_date, end_date) VALUES"
            " (%s, '{}'::jsonb, current_date, current_date) RETURNING id",
            (user_id,),
        )
        await conn.execute(
            "INSERT INTO trip_items (trip_id, day, ord, place_id, kind, starts_at, ends_at,"
            " visit_min) VALUES (%s, current_date, 1, %s, 'activity', now(),"
            " now() + interval '1 hour', 60)",
            (trip["id"], place_id),
        )


async def test_bonus_only_after_approval_once_and_balance(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    mine = (await env.client.get("/v1/me/bonuses", headers=headers)).json()
    assert mine == {"balance": 0, "tenge_per_bonus": 1, "items": [], "next_cursor": None}
    review = (
        await submit(env, headers, "review", pid, {"rating": 5, "text": "Прекрасное место"})
    ).json()
    assert await ledger(conn) == []  # published, "checked later": no bonus yet
    csrf = await logged_in(env.client, conn)

    await approve(env, conn, csrf, review["id"])
    rows = await ledger(conn)
    assert len(rows) == 1 and rows[0]["submission_id"].hex == review["id"].replace("-", "")
    # a review of a place with no reviews and no trips: 20 * age_max(2) * freq_min(1)
    assert rows[0]["amount"] == 40 and rows[0]["details"]["field_age_days"] is None
    assert rows[0]["idempotency_key"] == "submission:%s" % review["id"]

    again = await env.client.post(
        "/admin/moderation/%s/approve" % review["id"], data={"csrf_token": csrf}
    )
    assert again.headers["location"] == "/admin/moderation?done=already"
    assert len(await ledger(conn)) == 1

    body = (await env.client.get("/v1/me/bonuses", headers=headers)).json()
    assert body["balance"] == 40 and body["tenge_per_bonus"] == 1
    assert body["items"][0]["amount"] == 40 and body["items"][0]["submission_type"] == "review"
    assert (await env.client.get("/v1/me/bonuses")).status_code == 401


async def transit_row(conn):
    user = await fetch_one(conn, "INSERT INTO users DEFAULT VALUES RETURNING id")
    sub = await fetch_one(
        conn,
        "INSERT INTO submissions (user_id, type, payload, status)"
        " VALUES (%s, 'transit', '{}', 'approved') RETURNING id",
        (user["id"],),
    )
    return {"id": sub["id"], "user_id": user["id"], "type": "transit", "place_id": None,
            "place_photo_id": None}  # fmt: skip


async def test_ledger_key_is_unique_per_submission(conn):
    from app.submissions import bonuses

    row = await transit_row(conn)
    assert await bonuses.accrue(conn, row) == 60
    assert await bonuses.accrue(conn, row) is None  # same submission: nothing more
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM bonus_ledger"))["n"] == 1
    assert await bonuses.accrue(conn, {**row, "user_id": None}) is None  # anonymized author


async def test_rejected_and_auto_rejected_get_nothing(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    spam = (await submit(env, headers, "review", pid, {"rating": 1, "text": "x"})).json()
    assert spam["status"] == "rejected_auto"
    ok = (
        await submit(env, headers, "review", pid, {"rating": 3, "text": "Нормальное место"})
    ).json()
    csrf = await logged_in(env.client, conn)
    await env.client.post("/admin/moderation/%s/reject" % ok["id"], data={"csrf_token": csrf})
    assert await ledger(conn) == []
    body = (await env.client.get("/v1/me/bonuses", headers=headers)).json()
    assert body["balance"] == 0 and body["items"] == []


async def test_demand_depends_on_data_age_and_trips_and_excludes_own_data(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    user_id = (await fetch_one(conn, "SELECT id FROM users"))["id"]
    # a menu that is 90 days old and a place in 10 trips: 100 * 1.25 * 1.5
    await conn.execute(
        "INSERT INTO place_menu (place_id, payload, updated_at)"
        " VALUES (%s, '{}', now() - interval '90 days')", (pid,))  # fmt: skip
    await add_trips(conn, user_id, pid, 10)
    menu = (
        await submit(env, headers, "menu", pid, {"items": [{"name": "Плов", "price_kzt": 2500}]})
    ).json()
    # a photo: the user's own just-published photo must not make the place's photos "fresh"
    await conn.execute(
        "INSERT INTO place_photos (place_id, storage_key, status, created_at)"
        " VALUES (%s, 'old.jpg', 'approved', now() - interval '180 days')", (pid,))  # fmt: skip
    slot = await upload(env, headers, PNG)
    photo = (await submit(env, headers, "photo", pid, {"upload_id": slot["upload_id"]})).json()
    csrf = await logged_in(env.client, conn)
    await approve(env, conn, csrf, menu["id"])
    await approve(env, conn, csrf, photo["id"])
    amounts = {r["submission_type"]: r for r in await ledger(conn)}
    assert amounts["menu"]["amount"] == round(100 * 1.25 * 1.5)
    assert amounts["menu"]["details"]["trips"] == 10
    assert amounts["photo"]["amount"] == round(50 * 2 * 1.5)  # 180 days old = full age factor
    assert amounts["photo"]["details"]["field_age_days"] == pytest.approx(180, abs=1)


async def test_constants_from_the_admin_change_the_next_accrual(env, conn):
    pid = await place(conn)
    headers = await sign_in(conn)
    csrf = await logged_in(env.client, conn)
    page = await env.client.get("/admin/bonuses")
    assert page.status_code == 200 and 'name="base_review"' in page.text
    form = {k: "%g" % v for k, v in C.items()}
    bad = await env.client.post(
        "/admin/bonuses", data={**form, "csrf_token": csrf, "base_review": "x"}
    )
    assert bad.status_code == 422 and "Введите число" in bad.text
    forged = await env.client.post("/admin/bonuses", data={**form, "csrf_token": "no"})
    assert forged.status_code == 403
    ok = await env.client.post(
        "/admin/bonuses", data={**form, "csrf_token": csrf, "base_review": "11", "age_max": "3"}
    )
    assert ok.status_code == 303 and ok.headers["location"] == "/admin/bonuses?saved=1"
    review = (
        await submit(env, headers, "review", pid, {"rating": 5, "text": "Прекрасное место"})
    ).json()
    await approve(env, conn, csrf, review["id"])
    assert (await ledger(conn))[0]["amount"] == round(11 * 3 * 1)
    saved = await fetch_one(
        conn, "SELECT updated_by FROM demand_coefficients WHERE key = 'base_review'"
    )
    assert saved["updated_by"] is not None


# --- ledger integrity -------------------------------------------------------------------------


async def test_ledger_is_insert_only_but_goes_with_the_account(conn):
    from app.submissions import bonuses

    row = await transit_row(conn)
    user = {"id": row["user_id"]}
    await bonuses.accrue(conn, row)
    for statement in ("UPDATE bonus_ledger SET amount = 999", "DELETE FROM bonus_ledger"):
        with pytest.raises(psycopg.errors.RaiseException):
            async with conn.transaction():  # a savepoint: the failure must not poison the test
                await conn.execute(statement)
    assert (await fetch_one(conn, "SELECT amount FROM bonus_ledger"))["amount"] == 60
    await conn.execute("DELETE FROM users WHERE id = %s", (user["id"],))
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM bonus_ledger"))["n"] == 0
