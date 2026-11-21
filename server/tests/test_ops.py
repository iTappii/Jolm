"""Ш-51: liveness / readiness, metrics, error reporting hook, request id in logs."""

import json
import logging
from contextlib import asynccontextmanager

from pydantic import SecretStr

from app import metrics, observability
from app.config import Settings, get_settings
from app.main import create_app


async def test_livez_does_not_touch_the_database(client):
    class Broken:
        @asynccontextmanager
        async def transaction(self):
            raise ConnectionError("db down")
            yield

    client._transport.app.state.db = Broken()
    assert (await client.get("/livez")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).status_code == 503


async def test_readyz_matches_health(client):
    ready, health = await client.get("/readyz"), await client.get("/health")
    assert ready.status_code == health.status_code == 200 and ready.json() == health.json()


async def test_metrics_counts_requests_by_route_template(client):
    metrics.reset()
    await client.get("/v1/meta")
    await client.get("/v1/meta")
    await client.get("/nope")
    text = (await client.get("/metrics")).text
    assert 'jol_http_requests_total{method="GET",route="/v1/meta",status="200"} 2' in text
    assert 'route="unmatched",status="404"} 1' in text
    assert 'jol_http_request_duration_seconds_count{route="/v1/meta"} 2' in text
    assert "jol_jobs_pending " in text and "jol_jobs_dead " in text


async def test_metrics_needs_the_token_when_one_is_set(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "metrics_token", SecretStr("s3cret-token"))
    assert (await client.get("/metrics")).status_code == 401
    assert (
        await client.get("/metrics", headers={"Authorization": "Bearer nope"})
    ).status_code == 401
    ok = await client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
    assert ok.status_code == 200 and ok.headers["content-type"].startswith("text/plain")


async def test_metrics_is_hidden_outside_dev_without_a_token(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "prod")
    assert (await client.get("/metrics")).status_code == 404


def test_interactive_docs_are_off_in_prod(monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None, app_env="prod"))
    app = create_app()
    assert app.docs_url is None and app.openapi_url is None


def test_error_reporting_is_off_without_a_dsn_and_safe_without_the_sdk(caplog):
    assert observability.init_error_reporting(Settings(_env_file=None)) is False
    observability.capture_exception(RuntimeError("x"))  # no-op, must not raise
    import importlib.util

    if importlib.util.find_spec("sentry_sdk") is None:
        with caplog.at_level(logging.WARNING):
            assert (
                observability.init_error_reporting(
                    Settings(_env_file=None, sentry_dsn="https://k@example.invalid/1")
                )
                is False
            )
        assert "sentry-sdk is not installed" in caplog.text


async def test_unhandled_error_is_reported_with_the_request_id(client, monkeypatch):
    seen = []
    monkeypatch.setattr(
        observability, "capture_exception", lambda exc, request_id=None: seen.append(request_id)
    )

    @client._transport.app.get("/boom-ops-test")
    async def boom():
        raise RuntimeError("boom")

    client._transport.raise_app_exceptions = False
    r = await client.get("/boom-ops-test", headers={"X-Request-ID": "rid-123"})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert seen and seen[0] is not None


async def test_request_log_is_json_with_the_request_id(client, capfd):
    from app.logging_setup import setup_logging

    setup_logging("INFO")
    await client.get("/v1/meta", headers={"X-Request-ID": "rid-json-1"})
    lines = [
        json.loads(line) for line in capfd.readouterr().out.splitlines() if line.startswith("{")
    ]
    entry = next(
        e for e in lines if e.get("msg") == "request" and e.get("request_id") == "rid-json-1"
    )
    assert entry["status"] == 200 and entry["path"] == "/v1/meta" and "duration_ms" in entry
