"""Async HTTP client for fetching genome-annotation files (Mycobrowser GFF).

A thin wrapper around ``httpx.AsyncClient``: GETs a URL, follows redirects,
raises on HTTP error, and transparently gunzips ``.gz`` payloads so callers
always get decoded text. The ``httpx.AsyncClient`` is injected so tests supply a
``MockTransport`` and production configures timeouts. All parsing lives in the
pure ``mycobrowser_gff`` / ``dejesus_essentiality`` modules.

``fetch_text_secure`` is the SSRF-safe variant for admin-supplied URLs: it
delegates to :func:`~protcellar.infrastructure.ingestion.url_guard.fetch_bytes_guarded`
which follows redirects **manually** and validates every hop's ``Location``
against :func:`~protcellar.infrastructure.ingestion.url_guard.validate_public_url`
before connecting.  ``.gz`` decompression is applied after the guarded fetch so
legitimate gzip payloads still work.
"""

from __future__ import annotations

import gzip

import httpx

# Mycobrowser EPFL H37Rv genome annotation (plain GFF3, ~4.3 MB). The query
# string carries ``&`` — quote it when passing on a shell command line.
MYCOBROWSER_H37RV_GFF_URL = (
    "https://mycobrowser.epfl.ch/releases/5/get_file"
    "?dir=gff&file=Mycobacterium_tuberculosis_H37Rv.gff"
)


class MycobrowserClient:
    def __init__(self, client: httpx.AsyncClient, *, timeout: float = 120.0) -> None:
        self._client = client
        self._timeout = timeout

    async def fetch_text(self, url: str) -> str:
        """GET ``url`` and return its decoded text, gunzipping ``.gz`` payloads."""
        resp = await self._client.get(url, follow_redirects=True, timeout=self._timeout)
        resp.raise_for_status()
        if url.endswith(".gz"):
            return gzip.decompress(resp.content).decode("utf-8")
        return resp.text

    async def fetch_text_secure(self, url: str) -> str:
        """SSRF-safe variant of :meth:`fetch_text` for admin-supplied URLs.

        Uses :func:`~protcellar.infrastructure.ingestion.url_guard.fetch_bytes_guarded`
        to follow redirects manually, validating every hop's ``Location`` header
        before connecting.  After the guarded fetch, ``.gz`` payloads are
        decompressed so callers always receive decoded text.
        """
        from protcellar.infrastructure.ingestion.url_guard import fetch_bytes_guarded

        raw = await fetch_bytes_guarded(url, timeout=self._timeout)
        if url.endswith(".gz"):
            return gzip.decompress(raw).decode("utf-8")
        return raw.decode("utf-8")

    async def __aenter__(self) -> MycobrowserClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()
