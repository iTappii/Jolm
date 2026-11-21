"""Ш-23b (server): GET/PUT/DELETE /v1/me/favorites."""

from datetime import datetime, timezone

from app.db import execute, fetch_one
from app.favorites import api as favorites_api
from tests.test_chat import sign_in
from tests.test_places import add_place, load_categories


async def mk(conn, name="Парк", **kw):
    return await add_place(conn, name, 76.95, 43.25, **kw)


async def put(client, headers, pid):
    return await client.put("/v1/me/favorites/%s" % pid, headers=headers)


async def test_guest_gets_401_everywhere(client, conn):
    pid = await mk(conn)
    assert (await client.get("/v1/me/favorites")).status_code == 401
    assert (await client.put("/v1/me/favorites/%s" % pid)).status_code == 401
    assert (await client.delete("/v1/me/favorites/%s" % pid)).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert (await client.get("/v1/me/favorites", headers=bad)).status_code == 401


async def test_put_list_delete_and_idempotency(client, conn):
    await load_categories(conn)
    headers = await sign_in(conn)
    first, second = await mk(conn, "Первый"), await mk(conn, "Второй", category="museum")
    assert (await client.get("/v1/me/favorites", headers=headers)).json() == {"items": []}
    for _ in range(2):  # idempotent
        assert (await put(client, headers, first)).status_code == 204
    assert (await put(client, headers, second)).status_code == 204
    await execute(
        conn,
        "UPDATE user_favorites SET created_at = %s WHERE place_id = %s",
        (datetime(2026, 1, 1, tzinfo=timezone.utc), first),
    )
    response = await client.get("/v1/me/favorites", headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    items = response.json()["items"]
    assert [i["name"] for i in items] == ["Второй", "Первый"]  # newest first
    assert set(items[0]) == {
        "id", "name", "name_lang", "category", "kind", "lat", "lon", "is_public", "is_partner",
        "popularity", "address", "created_at",
    }  # fmt: skip
    assert items[0]["category"] == "museum" and items[0]["address"] is None
    assert abs(items[0]["lat"] - 43.25) < 1e-6 and abs(items[0]["lon"] - 76.95) < 1e-6
    assert (await client.delete("/v1/me/favorites/%s" % first, headers=headers)).status_code == 204
    assert (await client.delete("/v1/me/favorites/%s" % first, headers=headers)).status_code == 204
    assert [
        i["id"] for i in (await client.get("/v1/me/favorites", headers=headers)).json()["items"]
    ] == [str(second)]


async def test_names_follow_accept_language_and_address(client, conn):
    headers = await sign_in(conn)
    pid = await mk(conn, "Парк")
    await execute(
        conn,
        "UPDATE places SET name_en = 'Park', address_ru = 'ул. Абая', address_en = 'Abay st' "
        "WHERE id = %s",
        (pid,),
    )
    await put(client, headers, pid)
    ru = (
        await client.get("/v1/me/favorites", headers=dict(headers, **{"Accept-Language": "ru"}))
    ).json()["items"][0]
    en = (
        await client.get("/v1/me/favorites", headers=dict(headers, **{"Accept-Language": "en"}))
    ).json()["items"][0]
    assert (ru["name"], ru["address"]) == ("Парк", "ул. Абая")
    assert (en["name"], en["address"]) == ("Park", "Abay st")


async def test_put_unknown_or_inactive_place_is_404_and_delete_is_still_204(client, conn):
    headers = await sign_in(conn)
    hidden = await mk(conn, "Скрытое", status="hidden")
    for pid in (hidden, "00000000-0000-4000-8000-000000000000"):
        response = await put(client, headers, pid)
        assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
        assert (
            await client.delete("/v1/me/favorites/%s" % pid, headers=headers)
        ).status_code == 204
    assert (await put(client, headers, "not-a-uuid")).status_code == 422


async def test_favorites_are_per_user_and_hidden_places_are_not_listed(client, conn):
    a, b = await sign_in(conn, "a@example.com"), await sign_in(conn, "b@example.com")
    pid = await mk(conn)
    await put(client, a, pid)
    assert (await client.get("/v1/me/favorites", headers=b)).json() == {"items": []}
    await client.delete("/v1/me/favorites/%s" % pid, headers=b)  # b cannot remove a's
    assert len((await client.get("/v1/me/favorites", headers=a)).json()["items"]) == 1
    await execute(conn, "UPDATE places SET status = 'hidden' WHERE id = %s", (pid,))
    assert (await client.get("/v1/me/favorites", headers=a)).json() == {"items": []}
    n = (await fetch_one(conn, "SELECT count(*) AS n FROM user_favorites"))["n"]
    assert n == 1  # stored, just not shown


async def test_cap_applies_to_new_places_only(client, conn, monkeypatch):
    monkeypatch.setattr(favorites_api, "MAX_FAVORITES", 2)
    headers = await sign_in(conn)
    one, two, three = await mk(conn, "1"), await mk(conn, "2"), await mk(conn, "3")
    assert (await put(client, headers, one)).status_code == 204
    assert (await put(client, headers, two)).status_code == 204
    full = await put(client, headers, three)
    assert full.status_code == 409 and full.json()["error"]["code"] == "favorites_limit"
    assert (await put(client, headers, two)).status_code == 204  # already saved: no-op
    await client.delete("/v1/me/favorites/%s" % one, headers=headers)
    assert (await put(client, headers, three)).status_code == 204
