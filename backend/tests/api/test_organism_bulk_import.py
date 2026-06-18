import pytest
from httpx import AsyncClient

# Use tax IDs not used by test_organisms.py (which uses 9606, 562, 10090).
_REC = {
    "ncbi_tax_id": 1,
    "rank": "no rank",
    "scientific_name": "root",
    "source": "ncbi",
    "source_release": "2026_02",
    "source_record_id": "txid1",
    "source_record_checksum": "abc123",
}


@pytest.mark.asyncio
async def test_bulk_upsert_is_idempotent(client: AsyncClient) -> None:
    first = await client.post("/api/v1/organisms/bulk", json={"records": [_REC]})
    assert first.status_code == 200
    assert first.json()["summary"]["created"] == 1

    # Verify source_release is persisted and returned via GET
    created_id = first.json()["results"][0]["id"]
    get_resp = await client.get(f"/api/v1/organisms/{created_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["source_release"] == _REC["source_release"]

    # same checksum → skipped
    second = await client.post("/api/v1/organisms/bulk", json={"records": [_REC]})
    assert second.json()["summary"]["skipped"] == 1


@pytest.mark.asyncio
async def test_dry_run_does_not_persist(client: AsyncClient) -> None:
    rec = {
        **_REC,
        "ncbi_tax_id": 2,
        "source_record_id": "txid2",
        "scientific_name": "Bacteria",
    }
    dry = await client.post("/api/v1/organisms/bulk", json={"records": [rec], "dry_run": True})
    assert dry.json()["summary"]["created"] == 1
    # not actually persisted — resolve by NCBI tax_id should return 404
    resolved = await client.get("/api/v1/organisms/resolve/2")
    assert resolved.status_code == 404
