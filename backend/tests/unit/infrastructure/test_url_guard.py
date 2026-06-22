"""Unit tests for the SSRF URL guard.

All tests are HERMETIC — they use literal IP addresses so no real DNS is
needed.  The ``validate_public_url`` function calls ``socket.getaddrinfo``
internally; for literal IPs the OS returns the IP unchanged without network
I/O, so monkeypatching is unnecessary.
"""

from __future__ import annotations

import pytest

from protcellar.infrastructure.ingestion.url_guard import validate_public_url


# ---------------------------------------------------------------------------
# URLs that MUST raise ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",                         # loopback IPv4
        "http://127.0.0.1:8080/x",                    # loopback IPv4 with port
        "http://169.254.169.254/latest/meta-data/",   # link-local (AWS metadata)
        "http://10.0.0.1",                            # RFC1918 private class A
        "http://10.0.0.1/",                           # RFC1918 private class A (trailing slash)
        "http://172.16.0.1",                          # RFC1918 private class B
        "http://192.168.1.5",                         # RFC1918 private class C
        "http://[::1]/",                              # IPv6 loopback
        "http://0.0.0.0",                             # unspecified
        "ftp://8.8.8.8",                              # disallowed scheme
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
        "http://8.8.8.8/",                # Google public DNS — public literal IP
        "https://93.184.216.34/",          # example.com IP — public literal IP
        "https://1.1.1.1/",               # Cloudflare DNS — public literal IP
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
