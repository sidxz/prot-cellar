import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient, ncbi_tax_id: int) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": ncbi_tax_id, "rank": "species", "scientific_name": "Homo sapiens"},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_bulk_upsert_is_idempotent(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99901)
    rec = {
        "primary_accession": "P0DP23",
        "organism_id": organism_id,
        "sequence": "MADQLTEEQIAEFKEAFSLF",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "P0DP23",
        "source_record_checksum": "crc1",
        "cross_references": [{"database": "pdb", "accession": "6VXX"}],
    }
    first = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert first.status_code == 200
    assert first.json()["summary"]["created"] == 1

    # Verify cross_reference round-trips
    got_created = await client.get("/api/v1/proteins/P0DP23")
    xrefs = got_created.json()["cross_references"]
    assert any(x["database"] == "pdb" and x["accession"] == "6VXX" for x in xrefs)

    # Same checksum → skipped
    second = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert second.json()["summary"]["skipped"] == 1

    # Changed checksum → updated
    rec2 = {**rec, "source_record_checksum": "crc2", "sequence": "MADQLTEEQIAEFKEAFSLFD"}
    third = await client.post("/api/v1/proteins/bulk", json={"records": [rec2]})
    assert third.json()["summary"]["updated"] == 1
    got = await client.get("/api/v1/proteins/P0DP23")
    assert got.json()["seq_length"] == len("MADQLTEEQIAEFKEAFSLFD")


@pytest.mark.asyncio
async def test_bulk_dry_run_does_not_persist(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99902)
    rec = {
        "primary_accession": "Q8N158",
        "organism_id": organism_id,
        "sequence": "MKTAYIAKQR",
        "is_reviewed": False,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "Q8N158",
        "source_record_checksum": "crc1",
    }
    dry = await client.post("/api/v1/proteins/bulk", json={"records": [rec], "dry_run": True})
    assert dry.json()["summary"]["created"] == 1
    # Not persisted
    missing = await client.get("/api/v1/proteins/Q8N158")
    assert missing.status_code == 404
