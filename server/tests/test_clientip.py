"""Ш-51: the client IP behind a reverse proxy (X-Forwarded-For only from trusted proxies)."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.clientip import parse_networks, resolve_client_ip
from app.config import get_settings
from app.main import create_app

PROXIES = parse_networks("10.0.0.0/8, 192.168.1.5, fd00::/8")


def resolve(peer, *forwarded, networks=PROXIES):
    return resolve_client_ip(peer, list(forwarded), networks)


def test_no_trusted_proxies_means_the_peer_is_the_client():
    assert resolve("203.0.113.7", "1.2.3.4", networks=()) == "203.0.113.7"


def test_header_from_an_untrusted_peer_is_ignored():
    assert resolve("203.0.113.7", "1.2.3.4") == "203.0.113.7"


def test_trusted_proxy_reports_the_client():
    assert resolve("10.0.0.2", "198.51.100.9") == "198.51.100.9"


def test_missing_header_from_a_trusted_peer_is_the_peer():
    assert resolve("10.0.0.2") == "10.0.0.2"


def test_forged_left_entries_are_never_used():
    # the client sent "X-Forwarded-For: 1.2.3.4"; the proxy appended the client's real address
    assert resolve("10.0.0.2", "1.2.3.4, 198.51.100.9") == "198.51.100.9"
    assert resolve("10.0.0.2", "1.2.3.4", "198.51.100.9") == "198.51.100.9"  # two header lines


def test_chain_of_trusted_proxies_is_skipped_from_the_right():
    assert resolve("10.0.0.2", "198.51.100.9, 10.0.0.7, 192.168.1.5") == "198.51.100.9"


def test_forged_trusted_looking_entry_does_not_help_the_client():
    # client forges "10.1.1.1" hoping to look like a proxy; it still cannot pick the answer:
    # the rightmost untrusted address is the one our proxy saw
    assert resolve("10.0.0.2", "10.1.1.1, 198.51.100.9") == "198.51.100.9"


def test_all_hops_trusted_gives_the_leftmost():
    assert resolve("10.0.0.2", "10.0.0.5, 10.0.0.7") == "10.0.0.5"


def test_garbage_entry_stops_at_the_hop_to_its_right():
    assert resolve("10.0.0.2", "not-an-ip, 10.0.0.7") == "10.0.0.7"
    assert resolve("10.0.0.2", "evil") == "10.0.0.2"


def test_ipv6_and_mapped_addresses():
    assert resolve("fd00::1", "2001:db8::5") == "2001:db8::5"
    assert resolve("::ffff:10.0.0.2", "198.51.100.9") == "198.51.100.9"
    assert resolve("::ffff:203.0.113.7") == "203.0.113.7"
    assert resolve("10.0.0.2", "[2001:db8::5]") == "2001:db8::5"


def test_no_peer_is_unknown():
    assert resolve(None, "1.2.3.4") == "unknown"
    assert resolve("garbage", "1.2.3.4") == "unknown"


def test_bad_setting_is_rejected():
    with pytest.raises(ValueError):
        parse_networks("10.0.0.0/8, nonsense")


async def test_end_to_end_per_ip_limit_follows_the_real_client(conn, monkeypatch):
    """Behind a trusted proxy two clients get separate IP limits; a spoofed header gains nothing."""
    from tests.conftest import TransactionalDatabase

    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")
    monkeypatch.setattr(get_settings(), "auth_secret", SecretStr("fixture-" * 8))
    app = create_app()
    app.state.db = TransactionalDatabase(conn)
    app.state.geocode_limiter.limit = 2
    proxy = ASGITransport(app=app, client=("10.0.0.2", 4000))
    direct = ASGITransport(app=app, client=("203.0.113.50", 4000))
    params = {"lat": 43.25, "lon": 76.95}

    async def get(transport, xff):
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return (await c.get("/v1/geocode/reverse", params=params, headers=xff)).status_code

    assert [await get(proxy, {"X-Forwarded-For": "198.51.100.1"}) for _ in range(3)] == [
        200,
        200,
        429,
    ]
    # another real client behind the same proxy is not locked out by the first one
    assert await get(proxy, {"X-Forwarded-For": "198.51.100.2"}) == 200
    # a client of the proxy that forges the left side stays on its own address
    assert await get(proxy, {"X-Forwarded-For": "9.9.9.9, 198.51.100.1"}) == 429
    # a direct (untrusted) caller cannot choose its address with the header
    assert [await get(direct, {"X-Forwarded-For": "198.51.100.%d" % i}) for i in (7, 8, 9)] == [
        200,
        200,
        429,
    ]
