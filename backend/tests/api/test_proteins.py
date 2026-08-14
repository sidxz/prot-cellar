import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.infrastructure.persistence.sqlalchemy.gene_ontology.models import GoEdgeModel


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


async def _strain(client: AsyncClient, species_organism_id: str, name: str) -> str:
    resp = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_organism_id, "name": name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_protein_catalog_filters(client: AsyncClient) -> None:
    org = await _organism(client, 99930, "Filter testus")
    rich = {
        "primary_accession": "P0DV10",
        "organism_id": org,
        "sequence": "MKTAYIAKQR",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "x",
        "source_record_id": "P0DV10",
        "source_record_checksum": "c",
        "cross_references": [
            {"database": "PDB", "accession": "1XYZ"},
            {"database": "GO", "accession": "GO:0016491"},
        ],
        "keyword_refs": [{"kw_id": "KW-0560"}],
    }
    bare = {
        **rich,
        "primary_accession": "P0DV11",
        "source_record_id": "P0DV11",
        "cross_references": [],
        "keyword_refs": [],
    }
    resp = await client.post("/api/v1/proteins/bulk", json={"records": [rich, bare]})
    assert resp.status_code == 200

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
async def test_go_term_descendants_filter(client: AsyncClient, database_url: str) -> None:
    # seed a GO edge: child GO:0016655 is_a parent GO:0016491 (committed so the app sees it)
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        session.add(
            GoEdgeModel(child_go_id="GO:0016655", parent_go_id="GO:0016491", relation="is_a")
        )
    await engine.dispose()

    org = await _organism(client, 99940, "Subtree testus")
    rec = {
        "primary_accession": "P0DW50",
        "organism_id": org,
        "sequence": "MKTAYIAKQR",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "x",
        "source_record_id": "P0DW50",
        "source_record_checksum": "c",
        "cross_references": [{"database": "GO", "accession": "GO:0016655"}],
    }
    assert (await client.post("/api/v1/proteins/bulk", json={"records": [rec]})).status_code == 200

    async def accs(q: str) -> set[str]:
        items = (await client.get(f"/api/v1/proteins{q}&limit=200")).json()["items"]
        return {p["primary_accession"] for p in items}

    # exact: the protein is annotated with the child, not the parent -> not matched
    assert "P0DW50" not in await accs("?go_term=GO:0016491")
    # subtree: descendants of the parent include the child -> matched
    assert "P0DW50" in await accs("?go_term=GO:0016491&descendants=true")


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

    # Resolve via UUID — what cross-service callers hold (daikon nominations)
    by_id = await client.get(f"/api/v1/proteins/resolve/{body['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["primary_accession"] == "P12345"

    # An unknown UUID is a 404, never a fall-through to the accession pivots
    missing = await client.get("/api/v1/proteins/resolve/00000000-0000-0000-0000-000000000009")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_list_item_projects_gene_names_structure_and_chem(client: AsyncClient) -> None:
    org = await _organism(client, 99960, "Geneus listus")

    gene = await client.post(
        "/api/v1/genes",
        json={"primary_name": "rho", "organism_id": org, "synonyms": ["nusG", "Rv1297"]},
    )
    assert gene.status_code == 201
    gene_id = gene.json()["id"]

    created = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P0DZ01",
            "organism_id": org,
            "sequence": "MKTAYIAKQR",
            "is_reviewed": True,
            "gene_id": gene_id,
            "protein_names": {
                "recommended": "Transcription termination factor Rho",
                "short_names": ["Rho"],
                "ec_numbers": ["3.6.4.-"],
            },
            "cross_references": [
                {"database": "PDB", "accession": "1A62"},
                {"database": "PDB", "accession": "1A63"},
                {"database": "AlphaFoldDB", "accession": "P0DZ01"},
                {"database": "ChEMBL", "accession": "CHEMBL1234"},
            ],
        },
    )
    assert created.status_code == 201

    listed = await client.get(
        "/api/v1/proteins", params={"organism_id": org, "limit": 50, "include_total": True}
    )
    assert listed.status_code == 200
    body = listed.json()
    item = next(p for p in body["items"] if p["primary_accession"] == "P0DZ01")
    # flattened identity / gene summary
    assert item["gene"]["primary_name"] == "rho"
    assert item["gene"]["synonyms"] == ["nusG", "Rv1297"]
    # display_label is exposed on the embedded gene summary too (no locus field set here
    # via the create route, so it falls back to the symbol). Locus/ORF tiers are covered
    # by the gene-endpoint tests + gene_display_label unit tests.
    assert item["gene"]["display_label"] == "rho"
    assert item["recommended_name"] == "Transcription termination factor Rho"
    assert item["short_names"] == ["Rho"]
    assert item["ec_numbers"] == ["3.6.4.-"]
    # derived decision flags
    assert item["structure"] == {"pdb_count": 2, "has_alphafold": True}
    assert item["chem"] == {"has_chembl": True, "has_drugbank": False}
    # essentiality / human-ortholog facts live on the gene, not the protein list item
    assert "essential" not in item
    assert "has_human_homolog" not in item
    # total count is reported for the filtered set when requested
    assert body["total_count"] >= 1


@pytest.mark.asyncio
async def test_list_search_and_enzyme_filters(client: AsyncClient) -> None:
    org = await _organism(client, 99962, "Searchus testus")

    gene = await client.post(
        "/api/v1/genes",
        json={"primary_name": "katG", "organism_id": org, "synonyms": ["Rv1908c"]},
    )
    gene_id = gene.json()["id"]
    await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P0DZ10",
            "organism_id": org,
            "sequence": "MKTAYIAKQR",
            "is_reviewed": True,
            "gene_id": gene_id,
            "protein_names": {
                "recommended": "Catalase-peroxidase",
                "ec_numbers": ["1.11.1.21"],
            },
        },
    )
    # a non-enzyme with no gene
    await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P0DZ11",
            "organism_id": org,
            "sequence": "MKTAYIAKQR",
            "is_reviewed": True,
            "protein_names": {"recommended": "Uncharacterized protein"},
        },
    )

    async def accs(params: dict) -> set[str]:
        resp = await client.get("/api/v1/proteins", params={"organism_id": org, **params})
        return {p["primary_accession"] for p in resp.json()["items"]}

    # search by gene synonym (Rv locus), gene name, and protein name
    assert await accs({"q": "Rv1908c"}) == {"P0DZ10"}
    assert await accs({"q": "katg"}) == {"P0DZ10"}  # case-insensitive
    assert await accs({"q": "uncharacterized"}) == {"P0DZ11"}
    assert await accs({"q": "zzznomatch"}) == set()

    # enzyme filter keyed on presence of EC numbers
    assert await accs({"is_enzyme": "true"}) == {"P0DZ10"}
    assert await accs({"is_enzyme": "false"}) == {"P0DZ11"}


@pytest.mark.asyncio
async def test_list_protein_without_gene_has_null_gene(client: AsyncClient) -> None:
    org = await _organism(client, 99961, "Genelessus")
    created = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": "P0DZ02",
            "organism_id": org,
            "sequence": "MKTAYIAKQR",
            "is_reviewed": True,
        },
    )
    assert created.status_code == 201

    listed = await client.get("/api/v1/proteins", params={"organism_id": org, "limit": 50})
    item = next(p for p in listed.json()["items"] if p["primary_accession"] == "P0DZ02")
    assert item["gene"] is None


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


@pytest.mark.asyncio
async def test_protein_strain_filter_and_response(client: AsyncClient) -> None:
    """The list projection carries strain_id, and ?strain_id= narrows page + total."""
    org = await _organism(client, 99950, "Strain testus")
    s1 = await _strain(client, org, "Strain One")
    s2 = await _strain(client, org, "Strain Two")
    base = {
        "organism_id": org,
        "sequence": "MKTAYIAKQR",
        "is_reviewed": True,
        "source": "uniprot",
        "source_release": "x",
        "source_record_checksum": "c",
    }
    rec1 = {**base, "primary_accession": "P0DX01", "source_record_id": "P0DX01", "strain_id": s1}
    rec2 = {**base, "primary_accession": "P0DX02", "source_record_id": "P0DX02", "strain_id": s2}
    resp = await client.post("/api/v1/proteins/bulk", json={"records": [rec1, rec2]})
    assert resp.status_code == 200, resp.text

    # Each list row exposes its strain_id (needed for the catalog Strain column).
    listed = (await client.get("/api/v1/proteins?limit=200")).json()
    by_acc = {p["primary_accession"]: p for p in listed["items"]}
    assert by_acc["P0DX01"]["strain_id"] == s1
    assert by_acc["P0DX02"]["strain_id"] == s2
    # total_count is opt-in: plain listings (bulk data-view pulls) skip the extra COUNT scan.
    assert listed["total_count"] is None

    # Filtering by strain narrows both the page and the matching total.
    page = (
        await client.get(f"/api/v1/proteins?strain_id={s1}&limit=200&include_total=true")
    ).json()
    accs = {p["primary_accession"] for p in page["items"]}
    assert "P0DX01" in accs
    assert "P0DX02" not in accs
    assert page["total_count"] == 1
