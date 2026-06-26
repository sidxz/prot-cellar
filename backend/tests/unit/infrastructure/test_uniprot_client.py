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


@pytest.mark.asyncio
async def test_iter_entries_retries_transient_transport_error() -> None:
    """A transient TLS/connection drop on a page fetch must be retried, not abort
    the whole stream (regression: UP000005640 died at ~84.5k entries on
    httpx.ConnectError 'TLS/SSL connection has been closed (EOF)')."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/uniprotkb/search":
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectError("TLS/SSL connection has been closed (EOF)")
            return httpx.Response(200, json={"results": [{"primaryAccession": "P1"}]})
        return httpx.Response(404)

    http = httpx.AsyncClient(
        base_url="https://rest.uniprot.org", transport=httpx.MockTransport(handler)
    )
    async with http:
        uc = UniProtClient(http, backoff=0.0)
        accs = [e["primaryAccession"] async for e in uc.iter_entries("UP000000042")]
    assert accs == ["P1"]
    assert calls["n"] == 2  # failed once, retried, succeeded


@pytest.mark.asyncio
async def test_iter_entries_reraises_after_max_retries() -> None:
    """Persistent transport errors exhaust retries and surface, not loop forever."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("down")

    http = httpx.AsyncClient(
        base_url="https://rest.uniprot.org", transport=httpx.MockTransport(handler)
    )
    async with http:
        uc = UniProtClient(http, max_retries=3, backoff=0.0)
        with pytest.raises(httpx.ConnectError):
            _ = [e async for e in uc.iter_entries("UP000000042")]
    assert calls["n"] == 4  # initial + 3 retries
