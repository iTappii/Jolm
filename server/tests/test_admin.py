"""Admin panel: auth, CSRF, rate limit, places, curated routes, events, categories."""

import re

from app.admin import auth
from app.admin.api import place_form_values
from app.admin.service import get_place
from app.db import fetch_all, fetch_one

PASSWORD = "correct horse battery"
EMAIL = "admin@example.com"
CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


async def make_admin(conn, email=EMAIL, password=PASSWORD):
    await conn.execute(
        "INSERT INTO admins (email, password_hash) VALUES (%s, %s)",
        (email, auth.hash_password(password)),
    )


async def login(client, email=EMAIL, password=PASSWORD):
    page = await client.get("/admin/login")
    token = CSRF_RE.search(page.text).group(1)
    return await client.post(
        "/admin/login", data={"email": email, "password": password, "csrf_token": token}
    )


async def logged_in(client, conn):
    await make_admin(conn)
    resp = await login(client)
    assert resp.status_code == 303
    return await csrf_of(client)


async def csrf_of(client):
    return CSRF_RE.search((await client.get("/admin")).text).group(1)


async def add_place(conn, name_ru=None, name_en=None, category=None, popularity=0, **cols):
    row = await fetch_one(
        conn,
        """
        INSERT INTO places (name_ru, name_en, geom, category_id, popularity)
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(76.9, 43.2), 4326)::geography, %s, %s)
        RETURNING id
        """,
        (name_ru, name_en, category, popularity),
    )
    return str(row["id"])


async def add_category(conn, slug="cafe", name="Кафе"):
    row = await fetch_one(
        conn,
        "INSERT INTO place_categories (slug, name_ru, name_en) VALUES (%s, %s, %s) RETURNING id",
        (slug, name, slug),
    )
    return str(row["id"])


# ---------------------------------------------------------------- auth


async def test_login_page_and_redirect_when_anonymous(client):
    assert (await client.get("/admin/login")).status_code == 200
    resp = await client.get("/admin/places")
    assert resp.status_code == 303 and resp.headers["location"] == "/admin/login"
    resp = await client.post("/admin/places/x", data={})
    assert resp.status_code == 303


async def test_login_ok_sets_secure_session_and_stores_only_hash(client, conn):
    await make_admin(conn)
    resp = await login(client)
    assert resp.status_code == 303 and resp.headers["location"] == "/admin"
    set_cookie = resp.headers.get_list("set-cookie")
    session_header = next(c for c in set_cookie if c.startswith(auth.COOKIE_NAME + "="))
    assert "HttpOnly" in session_header and "SameSite=lax" in session_header
    assert "Max-Age=43200" in session_header
    token = client.cookies.get(auth.COOKIE_NAME)
    row = await fetch_one(
        conn, "SELECT token_hash, expires_at - created_at AS ttl FROM admin_sessions"
    )
    assert row["token_hash"] == auth.hash_token(token) and row["token_hash"] != token
    assert row["ttl"].total_seconds() == 12 * 3600
    page = await client.get("/admin")
    assert page.status_code == 200 and "Обзор" in page.text
    assert page.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in page.headers["content-security-policy"]


async def test_login_bad_password_and_unknown_email_look_the_same(client, conn):
    await make_admin(conn)
    bad = await login(client, password="wrong password!")
    unknown = await login(client, email="nobody@example.com")
    assert bad.status_code == unknown.status_code == 401
    assert "Неверный e-mail или пароль" in bad.text and "Неверный e-mail или пароль" in unknown.text
    assert auth.COOKIE_NAME not in client.cookies
    n = await fetch_one(conn, "SELECT count(*) AS n FROM admin_login_attempts")
    assert n["n"] == 2


async def test_login_is_case_insensitive_on_email(client, conn):
    await make_admin(conn)
    assert (await login(client, email="ADMIN@Example.com")).status_code == 303


async def test_disabled_admin_cannot_login(client, conn):
    await make_admin(conn)
    await conn.execute("UPDATE admins SET disabled_at = now()")
    assert (await login(client)).status_code == 401


async def test_login_rate_limit(client, conn):
    await make_admin(conn)
    for _ in range(5):
        assert (await login(client, password="wrong password!")).status_code == 401
    # even the right password is refused once the limit is hit
    resp = await login(client)
    assert resp.status_code == 429 and "Слишком много попыток" in resp.text
    assert auth.COOKIE_NAME not in client.cookies
    # a different e-mail from the same ip is still allowed (limit is per email+ip)
    await make_admin(conn, email="other@example.com")
    assert (await login(client, email="other@example.com")).status_code == 303


async def test_login_csrf_required(client, conn):
    await make_admin(conn)
    await client.get("/admin/login")
    resp = await client.post("/admin/login", data={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 403
    resp = await client.post(
        "/admin/login", data={"email": EMAIL, "password": PASSWORD, "csrf_token": "forged"}
    )
    assert resp.status_code == 403
    assert auth.COOKIE_NAME not in client.cookies


async def test_logout_revokes_session(client, conn):
    csrf = await logged_in(client, conn)
    old = client.cookies.get(auth.COOKIE_NAME)
    resp = await client.post("/admin/logout", data={"csrf_token": csrf})
    assert resp.status_code == 303
    client.cookies.set(auth.COOKIE_NAME, old, path="/admin")
    assert (await client.get("/admin/places")).status_code == 303
    row = await fetch_one(conn, "SELECT revoked_at FROM admin_sessions")
    assert row["revoked_at"] is not None


async def test_expired_session_rejected(client, conn):
    await logged_in(client, conn)
    await conn.execute("UPDATE admin_sessions SET expires_at = now() - interval '1 minute'")
    assert (await client.get("/admin/places")).status_code == 303


async def test_post_without_or_with_bad_csrf_is_rejected(client, conn):
    await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк", name_en="Park")
    place = await get_place(conn, place_id)
    form = place_form_values(place)
    form["entry_price_kzt"] = "999"
    resp = await client.post(f"/admin/places/{place_id}", data=form)
    assert resp.status_code == 403
    resp = await client.post(f"/admin/places/{place_id}", data=dict(form, csrf_token="forged"))
    assert resp.status_code == 403
    row = await fetch_one(conn, "SELECT entry_price_kzt FROM places WHERE id = %s", (place_id,))
    assert row["entry_price_kzt"] is None


async def test_csrf_token_of_another_session_rejected(client, conn):
    csrf = await logged_in(client, conn)
    await client.post("/admin/logout", data={"csrf_token": csrf})
    await login(client)  # new session -> new csrf
    place_id = await add_place(conn, name_ru="Парк")
    form = place_form_values(await get_place(conn, place_id))
    resp = await client.post(f"/admin/places/{place_id}", data=dict(form, csrf_token=csrf))
    assert resp.status_code == 403


# ---------------------------------------------------------------- places


async def test_place_search_filter_and_pagination(client, conn):
    await logged_in(client, conn)
    cafe = await add_category(conn)
    await add_place(conn, name_ru="Кафе Медеу", name_en="Medeu cafe", category=cafe)
    await add_place(conn, name_ru="Шымбулак", name_en="Shymbulak")
    await add_place(conn, name_ru="Скидка 50%", name_en="Fifty")

    resp = await client.get("/admin/places", params={"q": "MEDEU"})
    assert "Кафе Медеу" in resp.text and "Шымбулак" not in resp.text
    resp = await client.get("/admin/places", params={"q": "Шымб"})
    assert "Шымбулак" in resp.text and "Медеу" not in resp.text
    # LIKE wildcards are escaped: '%' matches only literal '%'
    resp = await client.get("/admin/places", params={"q": "%"})
    assert "Скидка 50%" in resp.text and "Шымбулак" not in resp.text
    resp = await client.get("/admin/places", params={"category": cafe})
    assert "Кафе Медеу" in resp.text and "Шымбулак" not in resp.text
    # htmx request returns only the results fragment
    resp = await client.get("/admin/places", params={"q": "medeu"}, headers={"HX-Request": "true"})
    assert "<html" not in resp.text and "Кафе Медеу" in resp.text

    for i in range(30):
        await add_place(conn, name_ru=f"Место {i:02d}", name_en="bulk")
    page1 = await client.get("/admin/places", params={"q": "bulk"})
    page2 = await client.get("/admin/places", params={"q": "bulk", "page": "2"})
    assert "Страница 1 из 2" in page1.text and "Страница 2 из 2" in page2.text
    names1 = set(re.findall(r"Место \d\d", page1.text))
    names2 = set(re.findall(r"Место \d\d", page2.text))
    assert len(names1) == 25 and len(names2) == 5 and not names1 & names2


async def test_place_search_sql_injection_is_inert(client, conn):
    await logged_in(client, conn)
    await add_place(conn, name_ru="Парк")
    resp = await client.get("/admin/places", params={"q": "'; DROP TABLE places; --"})
    assert resp.status_code == 200
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM places"))["n"] == 1


async def test_edit_price_and_hours_updates_manual_override(client, conn):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк", name_en="Park")
    await conn.execute("UPDATE places SET manual_override = '[\"name_ru\"]'::jsonb")
    form = place_form_values(await get_place(conn, place_id))
    form.update(
        entry_price_kzt="1500",
        hours_0="09:00-13:00\n14:00-18:00",
        hours_5="круглосуточно",
        is_mountain="on",
        csrf_token=csrf,
    )
    resp = await client.post(f"/admin/places/{place_id}", data=form)
    assert resp.status_code == 303 and resp.headers["location"].endswith("saved=1")

    row = await fetch_one(
        conn,
        "SELECT entry_price_kzt, is_mountain, name_ru, manual_override FROM places WHERE id = %s",
        (place_id,),
    )
    assert row["entry_price_kzt"] == 1500 and row["is_mountain"] is True
    # only changed fields are added (plus what was already there); untouched name_en is not
    assert set(row["manual_override"]) == {"name_ru", "entry_price_kzt", "is_mountain", "hours"}
    hours = await fetch_all(
        conn,
        "SELECT weekday, opens::text AS o, closes::text AS c FROM place_hours "
        "WHERE place_id = %s ORDER BY weekday, opens",
        (place_id,),
    )
    assert [(h["weekday"], h["o"], h["c"]) for h in hours] == [
        (0, "09:00:00", "13:00:00"),
        (0, "14:00:00", "18:00:00"),
        (5, "00:00:00", "23:59:00"),
    ]
    # the edit page shows the saved values
    page = await client.get(f"/admin/places/{place_id}")
    assert 'value="1500"' in page.text and "14:00-18:00" in page.text

    # editing hours only still protects them; unchanged resubmit changes nothing
    form = place_form_values(await get_place(conn, place_id))
    form.update(hours_0="10:00-12:00", csrf_token=csrf)
    await client.post(f"/admin/places/{place_id}", data=form)
    hours = await fetch_all(
        conn, "SELECT weekday FROM place_hours WHERE place_id = %s", (place_id,)
    )
    assert len(hours) == 2
    form = place_form_values(await get_place(conn, place_id))
    form["csrf_token"] = csrf
    resp = await client.post(f"/admin/places/{place_id}", data=form)
    assert resp.headers["location"].endswith("saved=nochange")


async def test_hours_only_edit_marks_hours(client, conn):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    form = place_form_values(await get_place(conn, place_id))
    form.update(hours_2="08:00-20:00", csrf_token=csrf)
    await client.post(f"/admin/places/{place_id}", data=form)
    row = await fetch_one(conn, "SELECT manual_override FROM places WHERE id = %s", (place_id,))
    assert row["manual_override"] == ["hours"]


async def test_edit_with_invalid_input_shows_errors_and_saves_nothing(client, conn):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    form = place_form_values(await get_place(conn, place_id))
    form.update(entry_price_kzt="-10", hours_1="9 to 5", status="weird", csrf_token=csrf)
    resp = await client.post(f"/admin/places/{place_id}", data=form)
    assert resp.status_code == 422
    assert "Допустимо от 0" in resp.text and "ЧЧ:ММ-ЧЧ:ММ" in resp.text
    assert "Недопустимый статус" in resp.text
    row = await fetch_one(conn, "SELECT entry_price_kzt, manual_override FROM places")
    assert row["entry_price_kzt"] is None and row["manual_override"] == []
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM place_hours"))["n"] == 0


async def test_edit_html_is_escaped(client, conn):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    form = place_form_values(await get_place(conn, place_id))
    form.update(name_en="<script>alert(1)</script>", csrf_token=csrf)
    await client.post(f"/admin/places/{place_id}", data=form)
    page = await client.get(f"/admin/places/{place_id}")
    assert "<script>alert(1)" not in page.text and "&lt;script&gt;" in page.text


async def test_unknown_place_is_404(client, conn):
    await logged_in(client, conn)
    assert (await client.get("/admin/places/not-a-uuid")).status_code == 404
    assert (
        await client.get("/admin/places/00000000-0000-0000-0000-000000000000")
    ).status_code == 404


async def test_place_photos_add_and_delete(client, conn):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Парк")
    resp = await client.post(
        f"/admin/places/{place_id}/photos", data={"storage_key": "places/a.jpg", "csrf_token": csrf}
    )
    assert resp.status_code == 303
    bad = await client.post(
        f"/admin/places/{place_id}/photos", data={"storage_key": "http://x/a", "csrf_token": csrf}
    )
    assert bad.status_code == 422
    photo = await fetch_one(conn, "SELECT id, storage_key, source FROM place_photos")
    assert photo["storage_key"] == "places/a.jpg" and photo["source"] == "team"
    await client.post(
        f"/admin/places/{place_id}/photos/{photo['id']}/delete", data={"csrf_token": csrf}
    )
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM place_photos"))["n"] == 0


# ---------------------------------------------------------------- categories


async def test_category_edit(client, conn):
    csrf = await logged_in(client, conn)
    cat = await add_category(conn)
    assert "cafe" in (await client.get("/admin/categories")).text
    resp = await client.post(
        f"/admin/categories/{cat}",
        data={
            "name_ru": "Кофейня",
            "name_en": "Coffee",
            "outdoor": "on",
            "sort_order": "7",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 303
    row = await fetch_one(
        conn, "SELECT name_ru, name_en, outdoor, sort_order FROM place_categories"
    )
    assert (row["name_ru"], row["name_en"], row["outdoor"], row["sort_order"]) == (
        "Кофейня",
        "Coffee",
        True,
        7,
    )
    bad = await client.post(
        f"/admin/categories/{cat}",
        data={"name_ru": "", "name_en": "x", "sort_order": "z", "csrf_token": csrf},
    )
    assert bad.status_code == 422


# ---------------------------------------------------------------- curated routes


async def test_curated_route_create_add_reorder_publish(client, conn):
    csrf = await logged_in(client, conn)
    a = await add_place(conn, name_ru="Медеу", name_en="Medeu")
    b = await add_place(conn, name_ru="Шымбулак", name_en="Shymbulak")
    c = await add_place(conn, name_ru="Кок-Тобе", name_en="Kok Tobe")

    resp = await client.post(
        "/admin/routes/new",
        data={"title_ru": "Горы за день", "title_en": "Mountains in a day", "csrf_token": csrf},
    )
    assert resp.status_code == 303
    route = await fetch_one(conn, "SELECT id, status FROM curated_routes")
    rid = str(route["id"])
    assert route["status"] == "draft" and resp.headers["location"].startswith(
        f"/admin/routes/{rid}"
    )

    # empty route cannot be published
    resp = await client.post(
        f"/admin/routes/{rid}/status", data={"status": "published", "csrf_token": csrf}
    )
    assert resp.status_code == 422 and "без мест" in resp.text

    # place search (htmx) offers add buttons
    found = await client.get(f"/admin/routes/{rid}/place-search", params={"q": "медеу"})
    assert "Добавить" in found.text and a in found.text

    for pid in (a, b, c):
        resp = await client.post(
            f"/admin/routes/{rid}/places", data={"place_id": pid, "csrf_token": csrf}
        )
        assert resp.status_code == 303
    dup = await client.post(f"/admin/routes/{rid}/places", data={"place_id": a, "csrf_token": csrf})
    assert dup.status_code == 422 and "уже в маршруте" in dup.text

    async def order():
        rows = await fetch_all(
            conn, "SELECT place_id::text AS p, ord FROM curated_route_items ORDER BY ord"
        )
        assert [r["ord"] for r in rows] == list(range(1, len(rows) + 1))
        return [r["p"] for r in rows]

    assert await order() == [a, b, c]
    item_c = (
        await fetch_one(conn, "SELECT id FROM curated_route_items WHERE place_id = %s", (c,))
    )["id"]
    await client.post(
        f"/admin/routes/{rid}/items/{item_c}/move", data={"direction": "up", "csrf_token": csrf}
    )
    assert await order() == [a, c, b]
    item_a = (
        await fetch_one(conn, "SELECT id FROM curated_route_items WHERE place_id = %s", (a,))
    )["id"]
    await client.post(
        f"/admin/routes/{rid}/items/{item_a}/move", data={"direction": "up", "csrf_token": csrf}
    )
    assert await order() == [a, c, b]  # already first: no-op
    await client.post(f"/admin/routes/{rid}/items/{item_a}/remove", data={"csrf_token": csrf})
    assert await order() == [c, b]

    resp = await client.post(
        f"/admin/routes/{rid}/status", data={"status": "published", "csrf_token": csrf}
    )
    assert resp.status_code == 303
    assert (await fetch_one(conn, "SELECT status FROM curated_routes"))["status"] == "published"
    assert "published" in (await client.get("/admin/routes")).text
    await client.post(f"/admin/routes/{rid}/status", data={"status": "draft", "csrf_token": csrf})
    assert (await fetch_one(conn, "SELECT status FROM curated_routes"))["status"] == "draft"

    # edit titles/descriptions
    await client.post(
        f"/admin/routes/{rid}",
        data={
            "title_ru": "Новое",
            "title_en": "New",
            "description_ru": "Описание",
            "description_en": "",
            "csrf_token": csrf,
        },
    )
    row = await fetch_one(
        conn, "SELECT title_ru, description_ru, description_en FROM curated_routes"
    )
    assert (row["title_ru"], row["description_ru"], row["description_en"]) == (
        "Новое",
        "Описание",
        None,
    )


async def test_route_requires_titles(client, conn):
    csrf = await logged_in(client, conn)
    resp = await client.post("/admin/routes/new", data={"title_ru": "x", "csrf_token": csrf})
    assert resp.status_code == 422
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM curated_routes"))["n"] == 0


# ---------------------------------------------------------------- events


async def test_event_create_edit_delete(client, conn):
    csrf = await logged_in(client, conn)
    place_id = await add_place(conn, name_ru="Арена")
    resp = await client.post(
        "/admin/events/new",
        data={
            "title_ru": "Концерт",
            "title_en": "Concert",
            "place_id": place_id,
            "starts_at": "2026-12-01T19:00",
            "ends_at": "2026-12-01T22:00",
            "price_kzt": "5000",
            "is_promoted": "on",
            "sponsor": "Organizer",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 303
    ev = await fetch_one(
        conn,
        "SELECT id, is_promoted, price_kzt, "
        "starts_at AT TIME ZONE 'Asia/Almaty' AS local, starts_at, "
        "place_id::text AS pid FROM events",
    )
    assert ev["is_promoted"] and ev["price_kzt"] == 5000 and ev["pid"] == place_id
    assert ev["local"].hour == 19 and ev["starts_at"].utcoffset().total_seconds() == 0
    page = await client.get("/admin/events")
    assert "Концерт" in page.text and "Реклама" in page.text
    edit = await client.get(f"/admin/events/{ev['id']}")
    assert 'value="2026-12-01T19:00"' in edit.text and "Арена" in edit.text

    bad = await client.post(
        f"/admin/events/{ev['id']}",
        data={
            "title_ru": "Концерт",
            "starts_at": "2026-12-01T19:00",
            "ends_at": "2026-12-01T10:00",
            "csrf_token": csrf,
        },
    )
    assert bad.status_code == 422 and "Окончание раньше начала" in bad.text
    missing_place = await client.post(
        "/admin/events/new",
        data={
            "title_ru": "X",
            "starts_at": "2026-12-01T19:00",
            "place_id": "00000000-0000-0000-0000-000000000000",
            "csrf_token": csrf,
        },
    )
    assert missing_place.status_code == 422

    await client.post(
        f"/admin/events/{ev['id']}",
        data={
            "title_ru": "Концерт 2",
            "starts_at": "2026-12-02T19:00",
            "lat": "43.25",
            "lon": "76.95",
            "csrf_token": csrf,
        },
    )
    row = await fetch_one(conn, "SELECT title_ru, is_promoted, ends_at, place_id FROM events")
    assert row["title_ru"] == "Концерт 2" and not row["is_promoted"] and row["place_id"] is None
    await client.post(f"/admin/events/{ev['id']}/delete", data={"csrf_token": csrf})
    assert (await fetch_one(conn, "SELECT count(*) AS n FROM events"))["n"] == 0


async def test_static_assets_served(client):
    resp = await client.get("/admin/static/htmx-1.9.12.min.js")
    assert resp.status_code == 200 and "htmx" in resp.text
    assert (await client.get("/admin/static/admin.css")).status_code == 200
