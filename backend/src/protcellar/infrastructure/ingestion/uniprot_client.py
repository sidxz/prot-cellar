"""Async UniProt REST client — fetch a proteome's metadata and stream its entries.

The ``httpx.AsyncClient`` is injected so tests supply a ``MockTransport`` and
production configures base_url / timeouts. Request + pagination logic lives
here; per-field mapping lives in ``uniprot_mapper``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx


class UniProtClient:
    def __init__(self, client: httpx.AsyncClient, *, page_size: int = 500) -> None:
        self._client = client
        self._page_size = page_size

    async def fetch_proteome(self, proteome_id: str) -> dict[str, Any]:
        """GET the proteome metadata record (organism, BUSCO, statistics, ...)."""
        resp = await self._client.get(f"/proteomes/{proteome_id}", params={"format": "json"})
        resp.raise_for_status()
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
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            for entry in resp.json().get("results", []):
                yield entry
            # The next-page URL already carries the cursor + size; drop our params.
            url = _next_link(resp.headers.get("link"))
            params = None


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
