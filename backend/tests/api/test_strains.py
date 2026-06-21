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
async def test_update_strain_increments_version(client: AsyncClient) -> None:
    # Create organism for species reference (use a unique tax_id for strain tests)
    org_resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": 1000563,
            "rank": "species",
            "scientific_name": "Shigella flexneri strain test",
        },
    )
    assert org_resp.status_code == 201
    species_id = org_resp.json()["id"]

    # Create strain
    resp = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "PAO1"},
    )
    assert resp.status_code == 201
    strain_id = resp.json()["id"]

    # Patch
    patch = await client.patch(
        f"/api/v1/strains/{strain_id}",
        json={"isolate": "Lab stock A"},
    )
    assert patch.status_code == 200
    assert patch.json()["version"] == 2
    assert patch.json()["isolate"] == "Lab stock A"


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


@pytest.mark.asyncio
async def test_patch_ncbi_taxon_id(client: AsyncClient) -> None:
    species_resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": 1000565,
            "rank": "species",
            "scientific_name": "Test species for ncbi_taxon_id",
        },
    )
    assert species_resp.status_code == 201
    species_id = species_resp.json()["id"]

    # Create strain without an NCBI taxon id
    create_resp = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "Test Strain"},
    )
    assert create_resp.status_code == 201
    strain_id = create_resp.json()["id"]
    assert create_resp.json()["ncbi_taxon_id"] is None

    # Patch to add the strain's NCBI taxon id
    patch_resp = await client.patch(
        f"/api/v1/strains/{strain_id}",
        json={"ncbi_taxon_id": 83332},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["ncbi_taxon_id"] == 83332
    assert patch_resp.json()["version"] == 2

    # Verify GET reflects the new value
    get_resp = await client.get(f"/api/v1/strains/{strain_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["ncbi_taxon_id"] == 83332
