import pytest
from httpx import AsyncClient


async def _make_organism(
    client: AsyncClient,
    ncbi_tax_id: int = 3702,
    scientific_name: str = "Arabidopsis thaliana",
) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": ncbi_tax_id, "rank": "species", "scientific_name": scientific_name},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_get_and_search_gene(client: AsyncClient) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=3702, scientific_name="Arabidopsis thaliana"
    )

    created = await client.post(
        "/api/v1/genes",
        json={
            "primary_name": "TP53",
            "organism_id": organism_id,
            "synonyms": ["P53"],
            "ncbi_gene_id": "7157",
            "ensembl_gene_id": "ENSG00000141510",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["primary_name"] == "TP53"
    assert body["ncbi_gene_url"] is not None
    gene_id = body["id"]

    fetched = await client.get(f"/api/v1/genes/{gene_id}")
    assert fetched.status_code == 200
    assert fetched.json()["ensembl_gene_id"] == "ENSG00000141510"

    found = await client.get("/api/v1/genes", params={"name": "TP5"})
    assert found.status_code == 200
    assert any(g["primary_name"] == "TP53" for g in found.json()["items"])


@pytest.mark.asyncio
async def test_update_gene_increments_version(client: AsyncClient) -> None:
    organism_id = await _make_organism(client, ncbi_tax_id=8355, scientific_name="Xenopus laevis")
    created = await client.post(
        "/api/v1/genes", json={"primary_name": "BRCA1", "organism_id": organism_id}
    )
    gene_id = created.json()["id"]
    assert created.json()["version"] == 1

    patched = await client.patch(f"/api/v1/genes/{gene_id}", json={"hgnc_id": "HGNC:1100"})
    assert patched.status_code == 200
    assert patched.json()["hgnc_id"] == "HGNC:1100"
    assert patched.json()["version"] == 2
