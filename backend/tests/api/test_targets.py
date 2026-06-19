import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 9606, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    if resp.status_code == 409:
        return (await client.get("/api/v1/organisms/resolve/9606")).json()["id"]
    return resp.json()["id"]


async def _protein(client: AsyncClient, organism_id: str, accession: str) -> str:
    resp = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": accession,
            "organism_id": organism_id,
            "sequence": "MKTAYIAKQR",
            "is_reviewed": True,
        },
    )
    if resp.status_code == 409:
        return (await client.get(f"/api/v1/proteins/{accession}")).json()["id"]
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_single_protein_target_and_get(client: AsyncClient) -> None:
    organism_id = await _organism(client)
    p1 = await _protein(client, organism_id, "P11111")
    resp = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "EGFR",
            "target_type": "single_protein",
            "components": [{"protein_id": p1, "relationship": "single_protein"}],
            "chembl_id": "CHEMBL203",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["pref_name"] == "EGFR"
    assert len(body["components"]) == 1
    assert body["chembl_url"] is not None

    got = await client.get(f"/api/v1/targets/{body['id']}")
    assert got.status_code == 200
    assert got.json()["target_type"] == "single_protein"


@pytest.mark.asyncio
async def test_single_protein_with_two_components_rejected(client: AsyncClient) -> None:
    organism_id = await _organism(client)
    p1 = await _protein(client, organism_id, "P22222")
    p2 = await _protein(client, organism_id, "P33333")
    resp = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "Bad single",
            "target_type": "single_protein",
            "components": [
                {"protein_id": p1, "relationship": "single_protein"},
                {"protein_id": p2, "relationship": "single_protein"},
            ],
        },
    )
    assert resp.status_code == 422  # cardinality invariant violated


@pytest.mark.asyncio
async def test_update_target_preserves_components(client: AsyncClient) -> None:
    """Child-collection round-trip: a PATCH that swaps components persists correctly
    despite the base repo's raw-UPDATE version bump + delete-orphan flush."""
    organism_id = await _organism(client)
    p1 = await _protein(client, organism_id, "P44444")
    p2 = await _protein(client, organism_id, "P55555")
    p3 = await _protein(client, organism_id, "P66666")

    created = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "GABA-A",
            "target_type": "protein_complex",
            "components": [
                {"protein_id": p1, "relationship": "protein_subunit"},
                {"protein_id": p2, "relationship": "protein_subunit"},
            ],
        },
    )
    assert created.status_code == 201
    target_id = created.json()["id"]
    assert created.json()["version"] == 1

    patched = await client.patch(
        f"/api/v1/targets/{target_id}",
        json={
            "components": [
                {"protein_id": p2, "relationship": "protein_subunit"},
                {"protein_id": p3, "relationship": "protein_subunit"},
            ]
        },
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2
    returned = {c["protein_id"] for c in patched.json()["components"]}
    assert returned == {p2, p3}

    # Re-fetch confirms the swap persisted (delete-orphan removed p1, added p3)
    refetched = await client.get(f"/api/v1/targets/{target_id}")
    assert {c["protein_id"] for c in refetched.json()["components"]} == {p2, p3}
    assert len(refetched.json()["components"]) == 2
