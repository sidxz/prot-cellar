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
        client, ncbi_tax_id=83332, scientific_name="Mycobacterium tuberculosis H37Rv"
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
        client, ncbi_tax_id=9606, scientific_name="Homo sapiens"
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
