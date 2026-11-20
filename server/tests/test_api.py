from contextlib import asynccontextmanager

from app import __version__
from app.i18n import pick_locale


async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": __version__}
    assert r.headers["x-request-id"]


async def test_health_db_down_returns_503_uniform_error(client):
    class Broken:
        @asynccontextmanager
        async def transaction(self):
            raise ConnectionError("db down")
            yield

    client._transport.app.state.db = Broken()
    r = await client.get("/health", headers={"Accept-Language": "ru"})
    assert r.status_code == 503
    assert r.json() == {"error": {"code": "db_unavailable", "message": "База данных недоступна"}}


async def test_meta(client):
    r = await client.get("/v1/meta")
    assert r.status_code == 200
    assert r.json()["version"] == __version__
    assert r.json()["min_ios_version"]


async def test_unknown_route_error_format_and_locale(client):
    en = await client.get("/nope", headers={"Accept-Language": "en-US,en;q=0.9"})
    ru = await client.get("/nope", headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5"})
    assert en.status_code == 404 and ru.status_code == 404
    assert en.json() == {"error": {"code": "not_found", "message": "Not found"}}
    assert ru.json()["error"]["message"] == "Не найдено"


async def test_request_id_is_echoed(client):
    r = await client.get("/v1/meta", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_pick_locale():
    assert pick_locale(None) == "en"
    assert pick_locale("fr-FR") == "en"
    assert pick_locale("en;q=0.5, ru;q=0.9") == "ru"
