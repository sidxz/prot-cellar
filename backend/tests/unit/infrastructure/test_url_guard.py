"""Unit tests for the SSRF URL guard.

All tests are HERMETIC — they use literal IP addresses so no real DNS is
needed.  The ``validate_public_url`` function calls ``socket.getaddrinfo``
internally; for literal IPs the OS returns the IP unchanged without network
I/O, so monkeypatching is unnecessary.

The ``fetch_bytes_guarded`` tests use ``unittest.mock.patch`` to replace the
``httpx.AsyncClient`` used inside the helper so no real network I/O occurs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from protcellar.infrastructure.ingestion.url_guard import fetch_bytes_guarded, validate_public_url

# ---------------------------------------------------------------------------
# URLs that MUST raise ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",  # loopback IPv4
        "http://127.0.0.1:8080/x",  # loopback IPv4 with port
        "http://169.254.169.254/latest/meta-data/",  # link-local (AWS metadata)
        "http://10.0.0.1",  # RFC1918 private class A
        "http://10.0.0.1/",  # RFC1918 private class A (trailing slash)
        "http://172.16.0.1",  # RFC1918 private class B
        "http://192.168.1.5",  # RFC1918 private class C
        "http://[::1]/",  # IPv6 loopback
        "http://0.0.0.0",  # unspecified
        "ftp://8.8.8.8",  # disallowed scheme
    ],
)
def test_blocked_urls_raise(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_url(url)


# ---------------------------------------------------------------------------
# URLs that MUST pass without raising
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8/",  # Google public DNS — public literal IP
        "https://93.184.216.34/",  # example.com IP — public literal IP
        "https://1.1.1.1/",  # Cloudflare DNS — public literal IP
    ],
)
def test_allowed_urls_pass(url: str) -> None:
    # Should not raise
    validate_public_url(url)


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_missing_scheme_raises() -> None:
    with pytest.raises(ValueError, match="scheme"):
        validate_public_url("//8.8.8.8/path")


def test_file_scheme_raises() -> None:
    with pytest.raises(ValueError, match="scheme"):
        validate_public_url("file:///etc/passwd")


def test_empty_hostname_raises() -> None:
    with pytest.raises(ValueError):
        validate_public_url("http:///path")


def test_ipv6_private_raises() -> None:
    # fc00::/7 is unique-local (private) in IPv6
    with pytest.raises(ValueError):
        validate_public_url("http://[fc00::1]/")


def test_ipv6_link_local_raises() -> None:
    # fe80::/10 is link-local
    with pytest.raises(ValueError):
        validate_public_url("http://[fe80::1]/")


# ---------------------------------------------------------------------------
# fetch_bytes_guarded — SSRF-safe byte fetch with manual redirect following
#
# These tests patch ``httpx.AsyncClient`` so no real network I/O occurs.  Each
# mocked response exposes ``is_redirect`` / ``headers`` / ``content`` /
# ``raise_for_status`` exactly as the helper consumes them.  Redirect targets
# use public literal IPs so they survive the per-hop ``validate_public_url``
# check — the behaviour under test is the *guard*, not DNS resolution.
# ---------------------------------------------------------------------------


def _mock_response(
    *, content: bytes = b"", is_redirect: bool = False, location: str = ""
) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.is_redirect = is_redirect
    resp.content = content
    resp.headers = {"location": location} if location else {}
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


def _patch_async_client(responses: list[MagicMock]) -> tuple[Any, AsyncMock]:
    """Patch ``httpx.AsyncClient`` so its ``.get`` yields *responses* in order.

    Returns the ``patch`` context manager and the ``AsyncMock`` standing in for
    ``client.get`` so callers can assert how many hops were actually made.
    """
    mock_get = AsyncMock(side_effect=responses)
    mock_http = MagicMock()
    mock_http.get = mock_get
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=mock_http)
    client.__aexit__ = AsyncMock(return_value=None)
    return patch("httpx.AsyncClient", return_value=client), mock_get


async def test_fetch_bytes_guarded_returns_content_on_success() -> None:
    patcher, mock_get = _patch_async_client([_mock_response(content=b"GFF\tdata\n")])
    with patcher:
        result = await fetch_bytes_guarded("http://8.8.8.8/genes.gff")
    assert result == b"GFF\tdata\n"
    assert mock_get.await_count == 1


async def test_fetch_bytes_guarded_blocked_initial_url_never_connects() -> None:
    # validate_public_url rejects the metadata endpoint before any HTTP call.
    patcher, mock_get = _patch_async_client([_mock_response(content=b"x")])
    with patcher, pytest.raises(ValueError):
        await fetch_bytes_guarded("http://169.254.169.254/latest/meta-data/")
    mock_get.assert_not_awaited()


async def test_fetch_bytes_guarded_redirect_to_internal_raises() -> None:
    # Initial URL is public, but the redirect Location points at the AWS
    # metadata endpoint — the per-hop guard must reject it and not connect.
    patcher, mock_get = _patch_async_client(
        [_mock_response(is_redirect=True, location="http://169.254.169.254/latest/meta-data/")]
    )
    with patcher, pytest.raises(ValueError):
        await fetch_bytes_guarded("http://8.8.8.8/redirect")
    assert mock_get.await_count == 1  # fetched the first hop, refused to follow


async def test_fetch_bytes_guarded_follows_public_redirect() -> None:
    patcher, mock_get = _patch_async_client(
        [
            _mock_response(is_redirect=True, location="https://1.1.1.1/final.gff"),
            _mock_response(content=b"final-bytes"),
        ]
    )
    with patcher:
        result = await fetch_bytes_guarded("http://8.8.8.8/start")
    assert result == b"final-bytes"
    assert mock_get.await_count == 2


async def test_fetch_bytes_guarded_too_many_redirects_raises() -> None:
    # Every hop is a public redirect, so the only stop condition is the cap.
    patcher, _ = _patch_async_client(
        [
            _mock_response(is_redirect=True, location="https://1.1.1.1/a"),
            _mock_response(is_redirect=True, location="https://8.8.8.8/b"),
            _mock_response(is_redirect=True, location="https://1.1.1.1/c"),
        ]
    )
    with patcher, pytest.raises(ValueError, match="Too many redirects"):
        await fetch_bytes_guarded("http://8.8.8.8/start", max_redirects=2)
