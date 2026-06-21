import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient, ncbi_tax_id: int) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": ncbi_tax_id,
            "rank": "species",
            "scientific_name": "Mycobacterium tuberculosis",
        },
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_gene_bulk_upsert_is_idempotent(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99951)
    rec = {
        "primary_name": "katG",
        "organism_id": organism_id,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "99951:Rv1908c",
        "source_record_checksum": "c1",
        "synonyms": ["Rv1908c"],
    }
    first = await client.post("/api/v1/genes/bulk", json={"records": [rec]})
    assert first.status_code == 200
    assert first.json()["summary"]["created"] == 1
    gene_id = first.json()["results"][0]["id"]

    got = await client.get(f"/api/v1/genes/{gene_id}")
    assert got.json()["primary_name"] == "katG"
    assert "Rv1908c" in got.json()["synonyms"]

    second = await client.post("/api/v1/genes/bulk", json={"records": [rec]})
    assert second.json()["summary"]["skipped"] == 1

    rec2 = {**rec, "source_record_checksum": "c2", "primary_name": "katG2"}
    third = await client.post("/api/v1/genes/bulk", json={"records": [rec2]})
    assert third.json()["summary"]["updated"] == 1
    assert (await client.get(f"/api/v1/genes/{gene_id}")).json()["primary_name"] == "katG2"


@pytest.mark.asyncio
async def test_gene_bulk_dry_run_does_not_persist(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99952)
    rec = {
        "primary_name": "dnaA",
        "organism_id": organism_id,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "99952:Rv0001",
        "source_record_checksum": "c1",
    }
    dry = await client.post("/api/v1/genes/bulk", json={"records": [rec], "dry_run": True})
    assert dry.json()["summary"]["created"] == 1
    listed = await client.get("/api/v1/genes", params={"name": "dnaA", "organism_id": organism_id})
    assert listed.json()["items"] == []
