import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.gene_annotation import (
    GeneAnnotation,
    GeneAnnotationAxis,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


async def _seed_gene(database_url: str, gene: Gene) -> Gene:
    """Persist a domain Gene directly (bypasses the API) for read-path tests."""
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    async with uow:
        await SQLAlchemyGeneRepository(uow).save(gene)
        await uow.commit()
    await engine.dispose()
    return gene


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


@pytest.mark.asyncio
async def test_gene_response_includes_location_and_annotations(
    client: AsyncClient, database_url: str
) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990001, scientific_name="Locus testus alpha"
    )
    gene = Gene.create(
        primary_name="rpoB",
        organism_id=uuid.UUID(organism_id),
        genomic_accession="NC_000962.3",
        genomic_start=759807,
        genomic_end=763325,
        genomic_strand="+",
        assembly="ASM19595v2",
        annotations=[
            GeneAnnotation(
                axis=GeneAnnotationAxis.VULNERABILITY,
                key="essentiality",
                value="essential",
                dataset="DeJesus 2017",
                condition="in vitro 7H9",
                evidence="PMID:28096490",
            )
        ],
    )
    await _seed_gene(database_url, gene)

    r = await client.get(f"/api/v1/genes/{gene.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["genomic_accession"] == "NC_000962.3"
    assert body["genomic_start"] == 759807
    assert body["genomic_end"] == 763325
    assert body["genomic_strand"] == "+"
    assert body["assembly"] == "ASM19595v2"
    assert body["length_bp"] == 763325 - 759807 + 1
    assert body["annotations"][0]["axis"] == "vulnerability"
    assert body["annotations"][0]["key"] == "essentiality"
    assert body["annotations"][0]["value"] == "essential"
    assert body["annotations"][0]["value_type"] == "categorical"
    assert body["annotations"][0]["dataset"] == "DeJesus 2017"
    assert body["annotations"][0]["condition"] == "in vitro 7H9"
    assert body["annotations"][0]["evidence"] == "PMID:28096490"


@pytest.mark.asyncio
async def test_gene_response_location_fields_default_null(client: AsyncClient) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990002, scientific_name="Locus testus beta"
    )
    created = await client.post(
        "/api/v1/genes", json={"primary_name": "EGFR", "organism_id": organism_id}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["genomic_accession"] is None
    assert body["genomic_start"] is None
    assert body["length_bp"] is None
    assert body["annotations"] == []


@pytest.mark.asyncio
async def test_create_gene_with_location_and_annotations(client: AsyncClient) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990003, scientific_name="Locus testus gamma"
    )
    created = await client.post(
        "/api/v1/genes",
        json={
            "primary_name": "katG",
            "organism_id": organism_id,
            "genomic_accession": "NC_000962.3",
            "genomic_start": 2153889,
            "genomic_end": 2156111,
            "genomic_strand": "+",
            "assembly": "ASM19595v2",
            "annotations": [
                {
                    "axis": "vulnerability",
                    "key": "essentiality",
                    "value": "non-essential",
                    "dataset": "DeJesus 2017",
                    "condition": "in vitro 7H9",
                }
            ],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["genomic_accession"] == "NC_000962.3"
    assert body["length_bp"] == 2156111 - 2153889 + 1
    assert body["annotations"][0]["axis"] == "vulnerability"
    assert body["annotations"][0]["value"] == "non-essential"
    assert body["annotations"][0]["dataset"] == "DeJesus 2017"
    # default value_type applied by the domain value object
    assert body["annotations"][0]["value_type"] == "categorical"


@pytest.mark.asyncio
async def test_patch_sets_location_and_vulnerability_annotation(client: AsyncClient) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990004, scientific_name="Locus testus delta"
    )
    created = await client.post(
        "/api/v1/genes", json={"primary_name": "inhA", "organism_id": organism_id}
    )
    gene_id = created.json()["id"]

    patched = await client.patch(
        f"/api/v1/genes/{gene_id}",
        json={
            "genomic_accession": "NC_000962.3",
            "genomic_start": 1674202,
            "genomic_end": 1675011,
            "genomic_strand": "+",
            "annotations": [
                {
                    "axis": "vulnerability",
                    "key": "essentiality",
                    "value": "essential",
                    "dataset": "DeJesus 2017",
                    "condition": "in vitro 7H9",
                }
            ],
        },
    )
    assert patched.status_code == 200

    body = (await client.get(f"/api/v1/genes/{gene_id}")).json()
    assert body["genomic_accession"] == "NC_000962.3"
    assert body["genomic_strand"] == "+"
    assert body["length_bp"] == 1675011 - 1674202 + 1
    assert body["annotations"][0]["value"] == "essential"
    assert body["annotations"][0]["dataset"] == "DeJesus 2017"


@pytest.mark.asyncio
async def test_patch_without_location_keys_leaves_them_untouched(client: AsyncClient) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990005, scientific_name="Locus testus epsilon"
    )
    created = await client.post(
        "/api/v1/genes",
        json={
            "primary_name": "rpoC",
            "organism_id": organism_id,
            "genomic_accession": "NC_000962.3",
            "genomic_start": 763370,
            "genomic_end": 767320,
            "genomic_strand": "+",
        },
    )
    gene_id = created.json()["id"]

    # Patch an unrelated field — location must survive.
    patched = await client.patch(f"/api/v1/genes/{gene_id}", json={"hgnc_id": "HGNC:9999"})
    assert patched.status_code == 200
    body = patched.json()
    assert body["genomic_accession"] == "NC_000962.3"
    assert body["genomic_start"] == 763370
