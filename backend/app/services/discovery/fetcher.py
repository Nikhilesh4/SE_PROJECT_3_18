"""Safe page fetching for the Enricher, Verifier and web-search agent.

Fetched pages are untrusted *data*. This module is the only door agents use to
reach arbitrary URLs, so it holds the guardrails:

* http/https only, no credentials in the URL
* refuses hosts that resolve to private / loopback / link-local addresses (SSRF)
* optional domain allowlist (FETCH_ALLOWED_DOMAINS)
* honours robots.txt (cached per host) and sets an honest User-Agent
* response size cap, redirect re-validation, per-host politeness delay
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.config import settings

logger = logging.getLogger("discovery.fetcher")

USER_AGENT = "UniCompassBot/1.0 (+student opportunity aggregator; respects robots.txt)"
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 4
TIMEOUT = 15.0
HOST_DELAY_SECONDS = 1.0

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_hit: dict[str, float] = {}
_lock = threading.Lock()


class FetchBlocked(Exception):
    """The URL was refused by a guardrail (not a network failure)."""


@dataclass
class Page:
    url: str
    status: int
    text: str
    content_type: str


def _allowed_domains() -> list[str]:
    return [d.strip().lower() for d in settings.FETCH_ALLOWED_DOMAINS.split(",") if d.strip()]


def check_url(url: str) -> str:
    """Raise FetchBlocked unless `url` is safe to request; returns the normalised URL."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise FetchBlocked("only http(s) URLs are allowed")
    if parsed.username or parsed.password:
        raise FetchBlocked("credentials in URLs are not allowed")
    host = parsed.hostname.lower()
    allowed = _allowed_domains()
    if allowed and not any(host == d or host.endswith("." + d) for d in allowed):
        raise FetchBlocked(f"{host} is not in the domain allowlist")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchBlocked(f"cannot resolve {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise FetchBlocked(f"{host} resolves to a non-public address")
    return parsed.geturl()


def _robots_ok(client: httpx.Client, url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    with _lock:
        if origin not in _robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                resp = client.get(f"{origin}/robots.txt", timeout=8)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                    _robots[origin] = parser
                else:
                    _robots[origin] = None  # no robots.txt → allowed
            except httpx.HTTPError:
                _robots[origin] = None
        parser = _robots[origin]
    return True if parser is None else parser.can_fetch(USER_AGENT, url)


def _politeness(host: str) -> None:
    with _lock:
        wait = _last_hit.get(host, 0) + HOST_DELAY_SECONDS - time.monotonic()
        _last_hit[host] = time.monotonic() + max(wait, 0)
    if wait > 0:
        time.sleep(wait)


def fetch_page(url: str, *, client: httpx.Client | None = None, check_robots: bool = True) -> Page:
    """GET a page with all guardrails. Raises FetchBlocked or httpx.HTTPError."""
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}, follow_redirects=False, timeout=TIMEOUT)
    try:
        current = check_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            if check_robots and not _robots_ok(client, current):
                raise FetchBlocked("disallowed by robots.txt")
            _politeness(urlparse(current).hostname or "")
            with client.stream("GET", current) as resp:
                if resp.is_redirect and resp.headers.get("location"):
                    current = check_url(urljoin(current, resp.headers["location"]))
                    continue
                chunks, size = [], 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
                return Page(current, resp.status_code, body, resp.headers.get("content-type", ""))
        raise FetchBlocked("too many redirects")
    finally:
        if own:
            client.close()


def link_is_alive(url: str) -> bool | None:
    """True/False if reachable; None when the check itself was blocked or inconclusive."""
    try:
        page = fetch_page(url, check_robots=False)
    except FetchBlocked:
        return None
    except httpx.HTTPError:
        return False
    if page.status in (404, 410):
        return False
    return page.status < 400 or page.status in (401, 403, 429)  # bot walls ≠ dead
