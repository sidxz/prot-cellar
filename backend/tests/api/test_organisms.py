import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_resolve_organism(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["scientific_name"] == "Homo sapiens"
    assert any(n["name_class"] == "scientific_name" for n in body["names"])

    resolved = await client.get("/api/v1/organisms/resolve/9606")
    assert resolved.status_code == 200
    assert resolved.json()["ncbi_tax_id"] == 9606


@pytest.mark.asyncio
async def test_search_by_name(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 562, "rank": "species", "scientific_name": "Escherichia coli"},
    )
    resp = await client.get("/api/v1/organisms", params={"name": "coli"})
    assert resp.status_code == 200
    assert any(o["scientific_name"] == "Escherichia coli" for o in resp.json())


@pytest.mark.asyncio
async def test_update_organism_preserves_names(client: AsyncClient) -> None:
    # Step 1: Create an organism (use a different tax_id to avoid conflict with other tests)
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 10090, "rank": "species", "scientific_name": "Mus musculus"},
    )
    assert resp.status_code == 201
    body = resp.json()
    organism_id = body["id"]
    assert body["version"] == 1
    # The scientific_name row must be present in names
    assert any(n["name_class"] == "scientific_name" for n in body["names"])

    # Step 2: PATCH a scalar field
    patch_resp = await client.patch(
        f"/api/v1/organisms/{organism_id}",
        json={"scientific_name": "Mus musculus L."},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["scientific_name"] == "Mus musculus L."
    assert patched["version"] == 2
    # Names collection must NOT be empty or duplicated after update
    names = patched["names"]
    assert len(names) > 0, "names array must not be empty after PATCH"
    scientific_names = [n for n in names if n["name_class"] == "scientific_name"]
    assert len(scientific_names) >= 1, "scientific_name entry must survive PATCH"

    # Step 3: GET the organism and confirm names are still intact
    get_resp = await client.get(f"/api/v1/organisms/{organism_id}")
    assert get_resp.status_code == 200
    gotten = get_resp.json()
    assert gotten["scientific_name"] == "Mus musculus L."
    assert gotten["version"] == 2
    assert len(gotten["names"]) > 0, "names array must not be empty after GET post-PATCH"
    assert any(n["name_class"] == "scientific_name" for n in gotten["names"]), (
        "scientific_name entry must be present after GET post-PATCH"
    )
