"""Async UniProt REST client — fetch a proteome's metadata and stream its entries.

The ``httpx.AsyncClient`` is injected so tests supply a ``MockTransport`` and
production configures base_url / timeouts. Request + pagination logic lives
here; per-field mapping lives in ``uniprot_mapper``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

# Statuses worth retrying: rate limiting + transient server-side errors.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class UniProtClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        page_size: int = 500,
        max_retries: int = 5,
        backoff: float = 0.5,
    ) -> None:
        self._client = client
        self._page_size = page_size
        self._max_retries = max_retries
        self._backoff = backoff

    async def fetch_proteome(self, proteome_id: str) -> dict[str, Any]:
        """GET the proteome metadata record (organism, BUSCO, statistics, ...)."""
        resp = await self._get(f"/proteomes/{proteome_id}", params={"format": "json"})
        data: dict[str, Any] = resp.json()
        return data

    async def iter_entries(self, proteome_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield every UniProtKB entry in the proteome, following the cursor pages."""
        url: str | None = "/uniprotkb/search"
        params: dict[str, str] | None = {
            "query": f"proteome:{proteome_id}",
            "format": "json",
            "size": str(self._page_size),
        }
        while url is not None:
            resp = await self._get(url, params=params)
            for entry in resp.json().get("results", []):
                yield entry
            # The next-page URL already carries the cursor + size; drop our params.
            url = _next_link(resp.headers.get("link"))
            params = None

    async def _get(self, url: str, *, params: dict[str, str] | None) -> httpx.Response:
        """GET with bounded exponential-backoff retry on transient failures.

        Long proteome streams (hundreds of cursor pages) reliably hit the odd
        transient TLS/connection drop or 5xx; without retry a single blip aborts
        the whole import (UP000005640 died at ~84.5k on a TLS EOF). Cursor pages
        are idempotent, so retrying the same URL is safe.
        """
        attempt = 0
        while True:
            try:
                resp = await self._client.get(url, params=params)
            except httpx.TransportError:
                if attempt >= self._max_retries:
                    raise
            else:
                if resp.status_code not in _RETRYABLE_STATUS or attempt >= self._max_retries:
                    resp.raise_for_status()
                    return resp
            await asyncio.sleep(self._backoff * (2**attempt))
            attempt += 1


def _next_link(link_header: str | None) -> str | None:
    """Extract the ``rel="next"`` URL from a UniProt ``Link`` response header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().lstrip("<").rstrip(">")
        if any("next" in seg and "rel" in seg for seg in segments[1:]):
            return url
    return None
