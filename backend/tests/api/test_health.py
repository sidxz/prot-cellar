import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_version(client: AsyncClient) -> None:
    resp = await client.get("/version")
    assert resp.status_code == 200
    assert "version" in resp.json()
