"""Optional allowlisted public-web collector. For controlled benchmark prefer frozen archive replay."""
from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse, urljoin
import httpx
from .storage import store_snapshot


def _validate_url(url: str, allowed_hosts: set[str]):
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443):
        raise ValueError("only HTTPS with standard port and no credentials is allowed")
    host = u.hostname.lower().rstrip(".")
    if host not in allowed_hosts:
        raise ValueError(f"host is not on the explicit allowlist: {host}")
    try:
        results = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise ValueError("hostname resolution failed") from exc
    if not results:
        raise ValueError("hostname has no addresses")
    for result in results:
        ip = ipaddress.ip_address(result[4][0])
        if not ip.is_global:
            raise ValueError("non-public resolved address is forbidden")


def collect_public(root, source_id: str, url: str, *, allowed_hosts: set[str],
                   max_bytes: int = 2_000_000, **metadata):
    """Restricted collection; not hardened against all DNS-rebinding cases.

    Use only with trusted user-selected URLs and a tight allowlist, not agent-proposed URLs.
    """
    allowed_hosts = {h.lower().rstrip(".") for h in allowed_hosts}
    current = url
    with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            _validate_url(current, allowed_hosts)
            with client.stream("GET", current, headers={"User-Agent": "SourceTrustResearch/0.1"}) as res:
                if res.status_code in (301, 302, 303, 307, 308):
                    location = res.headers.get("location")
                    if not location:
                        raise ValueError("redirect without Location")
                    current = urljoin(current, location)
                    continue
                res.raise_for_status()
                ct = res.headers.get("content-type", "").split(";")[0].lower()
                if ct not in ("text/html", "text/plain"):
                    raise ValueError("unsupported content type")
                blocks, size = [], 0
                for chunk in res.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("document exceeds byte limit")
                    blocks.append(chunk)
                return store_snapshot(root, source_id, url, b"".join(blocks), content_type=ct,
                    status=res.status_code, final_url=str(res.url), **metadata)
    raise ValueError("redirect limit exceeded")
