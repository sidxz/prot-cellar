"""Unit tests for the UniProt REST fetcher — mocked transport, no real network."""

from __future__ import annotations

import httpx
import pytest

from protcellar.infrastructure.ingestion.uniprot_client import UniProtClient

_NEXT_LINK = (
    "<https://rest.uniprot.org/uniprotkb/search"
    "?query=proteome:UP000000042&cursor=NEXT&size=500&format=json>; "
    'rel="next"'
)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/proteomes/UP000000042":
        return httpx.Response(200, json={"id": "UP000000042", "proteinCount": 3})
    if path == "/uniprotkb/search":
        if request.url.params.get("cursor") is None:
            return httpx.Response(
                200,
                json={"results": [{"primaryAccession": "P1"}, {"primaryAccession": "P2"}]},
                headers={"Link": _NEXT_LINK},
            )
        return httpx.Response(200, json={"results": [{"primaryAccession": "P3"}]})
    return httpx.Response(404)


def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://rest.uniprot.org", transport=httpx.MockTransport(_handler)
    )


@pytest.mark.asyncio
async def test_fetch_proteome() -> None:
    async with _http() as http:
        proteome = await UniProtClient(http).fetch_proteome("UP000000042")
    assert proteome["id"] == "UP000000042"
    assert proteome["proteinCount"] == 3


@pytest.mark.asyncio
async def test_iter_entries_follows_next_cursor() -> None:
    async with _http() as http:
        uc = UniProtClient(http)
        accs = [e["primaryAccession"] async for e in uc.iter_entries("UP000000042")]
    assert accs == ["P1", "P2", "P3"]
