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


@pytest.mark.asyncio
async def test_bulk_import_captures_annotation_scalars(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99903)
    rec = {
        "primary_accession": "P9WIE5",
        "organism_id": organism_id,
        "sequence": "MPEQHPPITETTTGAASNGCPV",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "P9WIE5",
        "source_record_checksum": "crc1",
        "annotation_score": 5,
        "fragment": "single",
        "uniparc_id": "UPI000012706D",
    }
    resp = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert resp.status_code == 200
    got = (await client.get("/api/v1/proteins/P9WIE5")).json()
    assert got.get("annotation_score") == 5
    assert got.get("fragment") == "single"
    assert got.get("uniparc_id") == "UPI000012706D"


@pytest.mark.asyncio
async def test_bulk_import_captures_features(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99904)
    rec = {
        "primary_accession": "P9WIE7",
        "organism_id": organism_id,
        "sequence": "MPEQHPPITETTTGAASNGCPVVGHM",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "P9WIE7",
        "source_record_checksum": "crc1",
        "features": [
            {
                "feature_type": "Active site",
                "start": 281,
                "end": 281,
                "description": "Proton acceptor",
                "feature_id": "ACT_SITE_KATG",
                "evidence": [{"evidenceCode": "ECO:0000255"}],
            },
            {"feature_type": "Binding site", "start": 100, "end": 102, "feature_id": "BIND_1"},
        ],
    }
    resp = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert resp.status_code == 200
    got = (await client.get("/api/v1/proteins/P9WIE7")).json()
    feats = got.get("features") or []
    assert len(feats) == 2
    active = next(f for f in feats if f["feature_type"] == "Active site")
    assert active["start"] == 281
    assert active["end"] == 281
    assert active["feature_id"] == "ACT_SITE_KATG"
    assert active["evidence"] == [{"evidenceCode": "ECO:0000255"}]


@pytest.mark.asyncio
async def test_bulk_import_captures_comments(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99905)
    rec = {
        "primary_accession": "P9WIE9",
        "organism_id": organism_id,
        "sequence": "MTEYKLVVVGAGGVGKSALTIQ",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "P9WIE9",
        "source_record_checksum": "crc1",
        "comments": [
            {"comment_type": "FUNCTION", "text": "Catalase-peroxidase."},
            {
                "comment_type": "CATALYTIC ACTIVITY",
                "payload": {"reaction": "2 H2O2 = O2 + 2 H2O", "ec": "1.11.1.21"},
                "evidence": [{"evidenceCode": "ECO:0000269"}],
            },
        ],
    }
    resp = await client.post("/api/v1/proteins/bulk", json={"records": [rec]})
    assert resp.status_code == 200
    got = (await client.get("/api/v1/proteins/P9WIE9")).json()
    comments = got.get("comments") or []
    assert len(comments) == 2
    func = next(c for c in comments if c["comment_type"] == "FUNCTION")
    assert func["text"] == "Catalase-peroxidase."
    cat = next(c for c in comments if c["comment_type"] == "CATALYTIC ACTIVITY")
    assert cat["payload"]["ec"] == "1.11.1.21"
    assert cat["evidence"] == [{"evidenceCode": "ECO:0000269"}]
