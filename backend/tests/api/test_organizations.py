import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_organization(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/organizations", json={"name": "Eurofins", "org_type": "cro"})
    assert resp.status_code == 201
    org_id = resp.json()["id"]
    assert resp.json()["version"] == 1

    got = await client.get(f"/api/v1/organizations/{org_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "Eurofins"


@pytest.mark.asyncio
async def test_duplicate_name_conflicts(client: AsyncClient) -> None:
    await client.post("/api/v1/organizations", json={"name": "Dup", "org_type": "academic"})
    resp = await client.post("/api/v1/organizations", json={"name": "Dup", "org_type": "vendor"})
    assert resp.status_code == 409
