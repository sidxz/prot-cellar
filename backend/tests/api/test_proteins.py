import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient, tax_id: int, name: str) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": tax_id, "rank": "species", "scientific_name": name},
    )
    if resp.status_code == 409:
        # Already exists — resolve to get the id
        resolved = await client.get(f"/api/v1/organisms/resolve/{tax_id}")
        assert resolved.status_code == 200
        return resolved.json()["id"]
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_protein_catalog_filters(client: AsyncClient) -> None:
    org = await _organism(client, 99930, "Filter testus")
    rich = {
        "primary_accession": "P0DV10", "organism_id": org, "sequence": "MKTAYIAKQR",
        "is_reviewed": True, "source": "uniprot", "source_release": "x",
        "source_record_id": "P0DV10", "source_record_checksum": "c",
        "cross_references": [
            {"database": "PDB", "accession": "1XYZ"},
            {"database": "GO", "accession": "GO:0016491"},
        ],
        "keyword_refs": [{"kw_id": "KW-0560"}],
    }
    bare = {
        **rich, "primary_accession": "P0DV11", "source_record_id": "P0DV11",
        "cross_references": [], "keyword_refs": [],
    }
    assert (await client.post("/api/v1/proteins/bulk", json={"records": [rich, bare]})).status_code == 200

    async def accs(q: str) -> set[str]:
        items = (await client.get(f"/api/v1/proteins{q}&limit=200")).json()["items"]
        return {p["primary_accession"] for p in items}

    pdb = await accs("?xref_db=PDB")
    assert "P0DV10" in pdb and "P0DV11" not in pdb
    structures = await accs("?has_structure=true")
    assert "P0DV10" in structures and "P0DV11" not in structures
    go = await accs("?go_term=GO:0016491")
    assert "P0DV10" in go and "P0DV11" not in go
    kw = await accs("?keyword=KW-0560")
    assert "P0DV10" in kw and "P0DV11" not in kw


@pytest.mark.asyncio
async def test_create_get_fasta_and_resolve_protein(client: AsyncClient) -> None:
    organism_id = await _organism(client, 9606, "Homo sapiens")
    created = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P12345",
            "organism_id": organism_id,
            "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ",
            "is_reviewed": True,
            "entry_name": "TEST_HUMAN",
            "protein_names": {"recommended": "Test protein"},
            "secondary_accessions": ["Q99998"],
            "protein_existence": "evidence_at_protein_level",
            "sequence_version": 1,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["primary_accession"] == "P12345"
    assert body["uniprot_url"] is not None
    assert body["seq_length"] == len("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ")

    # JSON fetch by accession
    got = await client.get("/api/v1/proteins/P12345")
    assert got.status_code == 200
    assert got.json()["entry_name"] == "TEST_HUMAN"

    # FASTA negotiation
    fasta = await client.get("/api/v1/proteins/P12345", params={"format": "fasta"})
    assert fasta.status_code == 200
    assert fasta.text.startswith(">sp|P12345|TEST_HUMAN")

    # Resolve via secondary accession → canonical primary
    resolved = await client.get("/api/v1/proteins/resolve/Q99998")
    assert resolved.status_code == 200
    assert resolved.json()["primary_accession"] == "P12345"


@pytest.mark.asyncio
async def test_invalid_accession_rejected_and_search_filters(client: AsyncClient) -> None:
    organism_id = await _organism(client, 562, "Escherichia coli")

    bad = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "nope",
            "organism_id": organism_id,
            "sequence": "MKT",
            "is_reviewed": False,
        },
    )
    assert bad.status_code == 422  # domain ValidationError → 422

    await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P0AEX9",
            "organism_id": organism_id,
            "sequence": "M" * 400,
            "is_reviewed": True,
        },
    )
    listed = await client.get(
        "/api/v1/proteins",
        params={"organism_id": organism_id, "reviewed": "true", "min_length": 100},
    )
    assert listed.status_code == 200
    accs = [p["primary_accession"] for p in listed.json()["items"]]
    assert "P0AEX9" in accs
