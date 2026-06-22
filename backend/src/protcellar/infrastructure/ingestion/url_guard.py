"""SSRF guard for admin-supplied URLs.

Provides three public helpers:

* :func:`validate_public_url` — synchronous; resolves the hostname with
  ``socket.getaddrinfo`` and rejects any result that lands on a loopback,
  private, link-local, reserved, multicast, or unspecified address.

* :func:`fetch_text_guarded` — async; follows redirects **manually** so that
  every hop's ``Location`` header is re-validated before the next request is
  sent, preventing open-redirect SSRF chains.  Returns decoded text.

* :func:`fetch_bytes_guarded` — same manual redirect loop with per-hop
  validation, but returns the raw ``bytes`` of the final response body so
  that callers can apply their own decoding (e.g. ``gzip`` decompression).
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse

# ---------------------------------------------------------------------------
# Synchronous guard
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = {"http", "https"}


def validate_public_url(url: str) -> None:
    """Raise :class:`ValueError` if *url* targets a non-public address.

    Checks:
    - scheme must be ``http`` or ``https``
    - hostname must be present
    - every address returned by ``getaddrinfo`` must be globally routable
      (not loopback / private / link-local / reserved / multicast / unspecified)
    """
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme {parsed.scheme!r} is not allowed; use http or https.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"URL {url!r} has no hostname.")

    # Strip trailing dot (FQDN notation) before resolving
    hostname = hostname.rstrip(".")

    # Determine port for getaddrinfo (None falls back to the scheme default)
    port: int | None = parsed.port  # already int or None

    try:
        results = socket.getaddrinfo(hostname, port)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        # sockaddr is (address, port) for IPv4, (address, port, flow, scope) for IPv6
        raw_addr = sockaddr[0]
        try:
            addr = ipaddress.ip_address(raw_addr)
        except ValueError as exc:
            raise ValueError(f"Cannot parse resolved address {raw_addr!r}.") from exc

        if addr.is_loopback:
            raise ValueError(f"URL {url!r} resolves to loopback address {addr}.")
        if addr.is_private:
            raise ValueError(f"URL {url!r} resolves to private address {addr}.")
        if addr.is_link_local:
            raise ValueError(f"URL {url!r} resolves to link-local address {addr}.")
        if addr.is_reserved:
            raise ValueError(f"URL {url!r} resolves to reserved address {addr}.")
        if addr.is_multicast:
            raise ValueError(f"URL {url!r} resolves to multicast address {addr}.")
        if addr.is_unspecified:
            raise ValueError(f"URL {url!r} resolves to unspecified address {addr}.")


# ---------------------------------------------------------------------------
# Async guarded fetch
# ---------------------------------------------------------------------------


async def fetch_text_guarded(
    url: str,
    *,
    timeout: float = 120.0,
    max_redirects: int = 5,
) -> str:
    """GET *url* with manual redirect following and SSRF validation on every hop.

    ``follow_redirects=False`` is used so that each ``Location`` header is
    passed through :func:`validate_public_url` before the client ever connects
    to the redirect target.  This prevents open-redirect / SSRF chains where
    the initial URL is public but a redirect bounces to an internal endpoint.

    Raises :class:`ValueError` if any URL (initial or redirect) fails the
    guard, or if the redirect chain exceeds *max_redirects*.
    """
    import httpx

    validate_public_url(url)

    current_url = url
    hops = 0

    async with httpx.AsyncClient() as http:
        while True:
            resp = await http.get(
                current_url,
                follow_redirects=False,
                timeout=timeout,
            )

            if resp.is_redirect:
                hops += 1
                if hops > max_redirects:
                    raise ValueError(f"Too many redirects (>{max_redirects}) fetching {url!r}.")
                location = resp.headers.get("location", "")
                # Resolve relative Location against current URL
                next_url = str(urllib.parse.urljoin(current_url, location))
                validate_public_url(next_url)
                current_url = next_url
                continue

            resp.raise_for_status()
            return resp.text


async def fetch_bytes_guarded(
    url: str,
    *,
    timeout: float = 120.0,
    max_redirects: int = 5,
) -> bytes:
    """GET *url* with manual redirect following and SSRF validation on every hop.

    Identical to :func:`fetch_text_guarded` but returns the raw response
    ``bytes`` instead of decoded text, so callers can apply their own
    content-type-specific decoding (e.g. ``gzip`` decompression of ``.gz``
    payloads).

    ``follow_redirects=False`` is used so that each ``Location`` header is
    passed through :func:`validate_public_url` before the client ever connects
    to the redirect target.  This prevents open-redirect / SSRF chains where
    the initial URL is public but a redirect bounces to an internal endpoint.

    Raises :class:`ValueError` if any URL (initial or redirect) fails the
    guard, or if the redirect chain exceeds *max_redirects*.
    """
    import httpx

    validate_public_url(url)

    current_url = url
    hops = 0

    async with httpx.AsyncClient() as http:
        while True:
            resp = await http.get(
                current_url,
                follow_redirects=False,
                timeout=timeout,
            )

            if resp.is_redirect:
                hops += 1
                if hops > max_redirects:
                    raise ValueError(f"Too many redirects (>{max_redirects}) fetching {url!r}.")
                location = resp.headers.get("location", "")
                # Resolve relative Location against current URL
                next_url = str(urllib.parse.urljoin(current_url, location))
                validate_public_url(next_url)
                current_url = next_url
                continue

            resp.raise_for_status()
            return resp.content
