import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_strain(client: AsyncClient) -> None:
    # First create an organism to use as species reference (use a unique tax_id for strain tests)
    org_resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": 1000562,
            "rank": "species",
            "scientific_name": "Escherichia coli strain test",
        },
    )
    assert org_resp.status_code == 201
    species_id = org_resp.json()["id"]

    # Create strain
    resp = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "K-12 MG1655"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "K-12 MG1655"
    assert data["version"] == 1
    strain_id = data["id"]

    # Get strain
    got = await client.get(f"/api/v1/strains/{strain_id}")
    assert got.status_code == 200
    assert got.json()["name"] == "K-12 MG1655"


@pytest.mark.asyncio
async def test_list_strains(client: AsyncClient) -> None:
    # Create organism (use a unique tax_id for strain tests)
    org_resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": 1000564,
            "rank": "species",
            "scientific_name": "Test species strain test",
        },
    )
    assert org_resp.status_code == 201
    species_id = org_resp.json()["id"]

    # Create two strains
    await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "Strain Alpha"},
    )
    await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "Strain Beta"},
    )

    # List
    list_resp = await client.get("/api/v1/strains")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    names = [i["name"] for i in items]
    assert "Strain Alpha" in names
    assert "Strain Beta" in names


# test_update_strain_increments_version and test_patch_ncbi_taxon_id were removed here:
# both created a strain then PATCHed it in the same call, which strains (reference data,
# design doc §1.5, same as organisms/proteomes) can no longer do — every strain now lives
# in SHARED_WORKSPACE_ID regardless of who creates it, and PATCH is owned-only, so it
# 404s unconditionally. See the identical note in test_organisms.py.
