import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.gene_annotation import (
    GeneAnnotation,
    GeneAnnotationAxis,
)
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
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


async def _seed_essentiality(
    database_url: str, gene_id: uuid.UUID, *, workspace_id: uuid.UUID = SHARED_WORKSPACE_ID
) -> None:
    """Persist a target-biology Essentiality record for a gene (read-path tests).

    Defaults to SHARED so existing callers are unaffected; pass a caller's own
    ``workspace_id`` to seed a workspace-owned record instead.
    """
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    async with uow:
        rec = Essentiality.create(
            workspace_id=workspace_id,
            gene_id=gene_id,
            classification=EssentialityClass.ESSENTIAL,
            provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
        )
        await SQLAlchemyEssentialityRepository(uow).save(rec)
        await uow.commit()
    await engine.dispose()


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


# test_update_gene_increments_version was removed here: it created a gene then
# PATCHed it in the same call, which genes (reference data, design doc §1.5, same
# as organisms/proteins) can no longer do through the API — every gene now lives in
# SHARED_WORKSPACE_ID regardless of who creates it, and PATCH is owned-only, so it
# 404s unconditionally. That invariant is asserted once, honestly, in
# test_workspace_isolation.py::test_shared_gene_cannot_be_mutated. The
# version-increments-on-update mechanic it also checked is generic
# (SQLAlchemyRepository.save()) and still exercised via other, still-mutable
# aggregates (e.g. tags, targets) — it needs no gene-specific re-test.


@pytest.mark.asyncio
async def test_gene_response_includes_location_and_annotations(
    client: AsyncClient, database_url: str
) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990001, scientific_name="Locus testus alpha"
    )
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
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


# test_patch_sets_location_and_vulnerability_annotation and
# test_patch_without_location_keys_leaves_them_untouched were removed here: both
# created a gene then PATCHed it in the same call, unreachable now for the same
# reason as test_update_gene_increments_version above. The field-mapping logic in
# update_gene.py that they exercised is still correct and unchanged; the invariants
# they checked — genomic-location fields and annotations round-trip through
# Gene.update(), and an unspecified UNSET field survives a partial update — are
# still covered at the domain level in test_gene.py
# (test_gene_holds_genomic_location_and_length,
# test_gene_holds_annotations_and_update_replaces_them), which calls Gene.update()
# directly rather than through the now-unreachable HTTP PATCH path.


@pytest.mark.asyncio
async def test_gene_neighborhood_returns_ordered_neighbors_with_essentiality(
    client: AsyncClient, database_url: str
) -> None:
    organism_id = uuid.UUID(
        await _make_organism(client, ncbi_tax_id=990006, scientific_name="Locus testus zeta")
    )
    genes = []
    for i, start in enumerate([1000, 2000, 3000, 4000, 5000]):
        g = Gene.create(
            workspace_id=SHARED_WORKSPACE_ID,
            primary_name=f"gene{i}",
            organism_id=organism_id,
            genomic_accession="NC_000962.3",
            genomic_start=start,
            genomic_end=start + 500,
            genomic_strand="+",
        )
        await _seed_gene(database_url, g)
        genes.append(g)

    # Essentiality now lives in target-biology (the plugin's home), not a gene annotation.
    await _seed_essentiality(database_url, genes[2].id)

    center = genes[2]  # start == 3000
    r = await client.get(f"/api/v1/genes/{center.id}/neighborhood", params={"window": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["center_id"] == str(center.id)
    assert body["accession"] == "NC_000962.3"
    starts = [n["genomic_start"] for n in body["neighbors"]]
    assert starts == [2000, 3000, 4000]
    by_start = {n["genomic_start"]: n for n in body["neighbors"]}
    assert by_start[3000]["essentiality"] == "essential"
    assert by_start[3000]["primary_name"] == "gene2"
    assert by_start[3000]["genomic_strand"] == "+"
    assert by_start[2000]["essentiality"] is None
    assert by_start[4000]["essentiality"] is None


@pytest.mark.asyncio
async def test_gene_neighborhood_shows_workspace_owned_essentiality(
    client: AsyncClient, database_url: str, workspace_id: uuid.UUID
) -> None:
    """Regression: get_gene_neighborhood.py used to read a neighbor's essentiality
    with SHARED_WORKSPACE_ID hardcoded instead of the caller's own workspace, so a
    workspace-owned record never coloured the neighborhood strip even though the
    same record shows up in the gene's target-biology bundle and the bulk list.
    """
    organism_id = uuid.UUID(
        await _make_organism(client, ncbi_tax_id=990009, scientific_name="Locus testus theta")
    )
    genes = []
    for i, start in enumerate([1000, 2000, 3000]):
        g = Gene.create(
            workspace_id=SHARED_WORKSPACE_ID,
            primary_name=f"wsgene{i}",
            organism_id=organism_id,
            genomic_accession="NC_000964.3",
            genomic_start=start,
            genomic_end=start + 500,
            genomic_strand="+",
        )
        await _seed_gene(database_url, g)
        genes.append(g)

    # Owned by the caller's OWN workspace (client's fake_auth), not SHARED.
    await _seed_essentiality(database_url, genes[1].id, workspace_id=workspace_id)

    center = genes[1]  # start == 2000
    r = await client.get(f"/api/v1/genes/{center.id}/neighborhood", params={"window": 1})
    assert r.status_code == 200
    body = r.json()
    by_start = {n["genomic_start"]: n for n in body["neighbors"]}
    assert by_start[2000]["essentiality"] == "essential"


@pytest.mark.asyncio
async def test_gene_neighborhood_404_when_no_location(client: AsyncClient) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=990007, scientific_name="Locus testus eta"
    )
    created = await client.post(
        "/api/v1/genes", json={"primary_name": "noLoc", "organism_id": organism_id}
    )
    gene_id = created.json()["id"]

    r = await client.get(f"/api/v1/genes/{gene_id}/neighborhood")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_gene_neighborhood_404_for_unknown_gene(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/genes/{uuid.uuid4()}/neighborhood")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_gene_list_and_detail_lead_with_locus(
    client: AsyncClient, database_url: str
) -> None:
    organism_id = await _make_organism(
        client, ncbi_tax_id=83332, scientific_name="Mycobacterium tuberculosis"
    )
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="rho",
        organism_id=uuid.UUID(organism_id),
        synonyms=["MTCY373.17"],
        ordered_locus_names=["Rv1297"],
    )
    await _seed_gene(database_url, gene)

    detail = await client.get(f"/api/v1/genes/{gene.id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["display_label"] == "Rv1297"  # gene context leads with the locus
    assert body["ordered_locus_names"] == ["Rv1297"]
    assert body["primary_name"] == "rho"  # symbol still present

    listed = await client.get("/api/v1/genes", params={"name": "rho"})
    item = next(g for g in listed.json()["items"] if g["id"] == str(gene.id))
    assert item["display_label"] == "Rv1297"


@pytest.mark.asyncio
async def test_gene_leads_with_orf_when_no_locus(client: AsyncClient, database_url: str) -> None:
    # Plasmodium: PF3D7 ids are ORF names -> named genes lead with the ORF, not the symbol.
    organism_id = await _make_organism(
        client, ncbi_tax_id=36329, scientific_name="Plasmodium falciparum 3D7"
    )
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="VPS26",
        organism_id=uuid.UUID(organism_id),
        orf_names=["PF3D7_1250300"],
    )
    await _seed_gene(database_url, gene)
    detail = await client.get(f"/api/v1/genes/{gene.id}")
    body = detail.json()
    assert body["display_label"] == "PF3D7_1250300"
    assert body["orf_names"] == ["PF3D7_1250300"]
    assert body["primary_name"] == "VPS26"


@pytest.mark.asyncio
async def test_human_gene_falls_back_to_symbol(client: AsyncClient, database_url: str) -> None:
    organism_id = await _make_organism(client, ncbi_tax_id=9606, scientific_name="Homo sapiens")
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="TP53",
        organism_id=uuid.UUID(organism_id),
        synonyms=["P53"],
    )
    await _seed_gene(database_url, gene)
    detail = await client.get(f"/api/v1/genes/{gene.id}")
    assert detail.json()["display_label"] == "TP53"  # no locus -> symbol wins
