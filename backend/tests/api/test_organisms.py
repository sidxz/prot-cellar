import random

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_resolve_organism(client: AsyncClient) -> None:
    # Random tax_id: 9606 is also created by other test files sharing this DB.
    tax_id = random.randint(200_000, 999_999)
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": tax_id, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["scientific_name"] == "Homo sapiens"
    assert any(n["name_class"] == "scientific_name" for n in body["names"])

    resolved = await client.get(f"/api/v1/organisms/resolve/{tax_id}")
    assert resolved.status_code == 200
    assert resolved.json()["ncbi_tax_id"] == tax_id


@pytest.mark.asyncio
async def test_search_by_name(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 562, "rank": "species", "scientific_name": "Escherichia coli"},
    )
    resp = await client.get("/api/v1/organisms", params={"name": "coli"})
    assert resp.status_code == 200
    assert any(o["scientific_name"] == "Escherichia coli" for o in resp.json()["items"])


# test_reference_strain_must_belong_to_organism and test_update_organism_preserves_names
# were removed here: both created an organism then PATCHed it in the same call, which
# organisms (reference data, design doc §1.5) can no longer do — every organism now
# lives in SHARED_WORKSPACE_ID regardless of who creates it, and PATCH is owned-only, so
# it 404s unconditionally. That invariant is asserted once, honestly, in
# test_workspace_isolation.py::test_shared_organism_cannot_be_mutated. Re-asserting it
# here under names that promised strain validation / name preservation would be
# misleading — those code paths in update_organism.py still exist and are still
# correct, they are just unreachable through the API now that no tenant can own an
# organism to trigger them.
