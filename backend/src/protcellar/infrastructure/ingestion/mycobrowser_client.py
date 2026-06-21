"""Async HTTP client for fetching genome-annotation files (Mycobrowser GFF).

A thin wrapper around ``httpx.AsyncClient``: GETs a URL, follows redirects,
raises on HTTP error, and transparently gunzips ``.gz`` payloads so callers
always get decoded text. The ``httpx.AsyncClient`` is injected so tests supply a
``MockTransport`` and production configures timeouts. All parsing lives in the
pure ``mycobrowser_gff`` / ``dejesus_essentiality`` modules.
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

    async def __aenter__(self) -> MycobrowserClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()
