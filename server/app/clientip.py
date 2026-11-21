"""The client's IP address, the one place that decides it (Ш-51; reviews Ш-10 №1, Ш-25 №1).

Behind a reverse proxy the TCP peer is the proxy, so every client would share one address and the
per-IP limits (OTP, guest chat, geocode, analytics, admin login) would lock everybody out at once.
`X-Forwarded-For` is honoured ONLY when the direct peer is in `TRUSTED_PROXIES` (comma-separated
IPs / CIDRs, empty = nobody is trusted = the peer is the client). The header is then read from
the right: every hop that is itself a trusted proxy is skipped, and the first address that is not
trusted is the client. Anything the client wrote to the left of that hop is never looked at, so a
forged `X-Forwarded-For: 1.2.3.4` sent by a client only ever moves the answer to the client's own
real address. An unparsable entry stops the walk at the hop to its right.

Run uvicorn with `--no-proxy-headers`: its own X-Forwarded-For handling would rewrite
`request.client` before this module runs (infra/Dockerfile.api and `make run` do).
"""

import logging
from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from typing import List, Optional, Tuple, Union

from starlette.requests import Request

from app.config import get_settings

log = logging.getLogger(__name__)
UNKNOWN = "unknown"
Address = Union[IPv4Address, IPv6Address]


@lru_cache(maxsize=16)
def parse_networks(raw: str) -> Tuple:
    networks = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ip_network(part, strict=False))
        except ValueError:
            raise ValueError("TRUSTED_PROXIES: %r is not an IP address or CIDR" % part) from None
    return tuple(networks)


def _parse(raw: str) -> Optional[Address]:
    try:
        address = ip_address(raw.strip().strip("[]"))
    except ValueError:
        return None
    if isinstance(address, IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address


def _trusted(address: Address, networks: Tuple) -> bool:
    return any(address.version == n.version and address in n for n in networks)


def resolve_client_ip(peer: Optional[str], forwarded_for: List[str], networks: Tuple) -> str:
    """Pure core: `forwarded_for` is the list of X-Forwarded-For header values."""
    peer_address = _parse(peer) if peer else None
    if peer_address is None:
        return UNKNOWN
    if not networks or not _trusted(peer_address, networks):
        return str(peer_address)
    hops = [h.strip() for value in forwarded_for for h in value.split(",") if h.strip()]
    nearest = peer_address  # the hop to the right of the entry being examined
    for hop in reversed(hops):
        address = _parse(hop)
        if address is None:
            return str(nearest)
        if not _trusted(address, networks):
            return str(address)
        nearest = address
    return str(nearest)  # every hop is a trusted proxy: the leftmost one is the best we know


def client_ip(request: Request) -> str:
    networks = parse_networks(get_settings().trusted_proxies)
    peer = request.client.host if request.client else None
    return resolve_client_ip(peer, request.headers.getlist("x-forwarded-for"), networks)
