"""API tests for the target-biology bundle read endpoints."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from protcellar.domain.target_biology.vulnerability import Vulnerability
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.protein_production_repository import (  # noqa: E501
    SQLAlchemyProteinProductionRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.resistance_mutation_repository import (  # noqa: E501
    SQLAlchemyResistanceMutationRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.unpublished_structure_repository import (  # noqa: E501
    SQLAlchemyUnpublishedStructureRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.vulnerability_repository import (  # noqa: E501
    SQLAlchemyVulnerabilityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

WS = SHARED_WORKSPACE_ID


async def _save(database_url: str, repo_cls: type, aggregate: object) -> None:
    engine = create_async_engine(database_url)
    uow = AsyncUnitOfWork(async_sessionmaker(engine, expire_on_commit=False))
    async with uow:
        await repo_cls(uow).save(aggregate)  # type: ignore[operator]
        await uow.commit()
    await engine.dispose()


_FIXTURE_ORGANISM_TAX_ID = 941099
_FIXTURE_ORGANISM_NAME = "Fixturus testus"


async def _seed_gene(client: AsyncClient, database_url: str) -> uuid.UUID:
    """A real, SHARED gene for create-route tests now that Task 10 (parent
    validation) rejects a gene_id that was never persisted. genes.organism_id
    is FK-constrained, so a real organism (``_make_organism``, defined below
    and dedup-safe across calls) has to exist first.
    """
    organism_id = await _make_organism(client, _FIXTURE_ORGANISM_TAX_ID, _FIXTURE_ORGANISM_NAME)
    gene = Gene.create(
        workspace_id=WS, primary_name="tb-fixture-gene", organism_id=uuid.UUID(organism_id)
    )
    await _save(database_url, SQLAlchemyGeneRepository, gene)
    return gene.id


async def _seed_protein(client: AsyncClient, database_url: str) -> uuid.UUID:
    """Same as ``_seed_gene``, protein side. ``primary_accession`` is
    regex-validated UniProt syntax and unique per row, so it's derived from a
    fresh uuid4 rather than hardcoded.
    """
    organism_id = await _make_organism(client, _FIXTURE_ORGANISM_TAX_ID, _FIXTURE_ORGANISM_NAME)
    h = uuid.uuid4().hex
    accession = f"Q{int(h[0], 16) % 10}{h[1:4].upper()}{int(h[4], 16) % 10}"
    protein = Protein.create(
        workspace_id=WS,
        primary_accession=accession,
        organism_id=uuid.UUID(organism_id),
        sequence="MSTNPKPQRSTV",
        is_reviewed=True,
    )
    await _save(database_url, SQLAlchemyProteinRepository, protein)
    return protein.id


@pytest.mark.asyncio
async def test_gene_target_biology_bundle(client: AsyncClient, database_url: str) -> None:
    gene_id = uuid.uuid4()
    prov = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        citations=(Citation(pmid="28096490"),),
    )
    await _save(
        database_url,
        SQLAlchemyVulnerabilityRepository,
        Vulnerability(workspace_id=WS, gene_id=gene_id, provenance=prov, vulnerability_score=0.82),
    )
    await _save(
        database_url,
        SQLAlchemyResistanceMutationRepository,
        ResistanceMutation(
            workspace_id=WS,
            gene_id=gene_id,
            mutation="S315T",
            provenance=prov,
            compound=CompoundRef(compound_id=uuid.uuid4(), name="isoniazid"),
        ),
    )
    # Essentiality on a *different* gene must not leak into this bundle.
    await _save(
        database_url,
        SQLAlchemyEssentialityRepository,
        Essentiality(
            workspace_id=WS,
            gene_id=uuid.uuid4(),
            classification=EssentialityClass.ESSENTIAL,
            provenance=prov,
        ),
    )

    r = await client.get(f"/api/v1/genes/{gene_id}/target-biology")
    assert r.status_code == 200
    body = r.json()
    assert len(body["vulnerability"]) == 1
    assert body["vulnerability"][0]["vulnerability_score"] == 0.82
    assert body["vulnerability"][0]["provenance"]["citations"][0]["pmid"] == "28096490"
    assert body["vulnerability"][0]["provenance"]["source_type"] == "published"
    assert len(body["resistance_mutation"]) == 1
    assert body["resistance_mutation"][0]["mutation"] == "S315T"
    assert body["resistance_mutation"][0]["compound"]["name"] == "isoniazid"
    assert body["essentiality"] == []  # the other gene's record didn't leak


@pytest.mark.asyncio
async def test_protein_target_biology_bundle(client: AsyncClient, database_url: str) -> None:
    protein_id = uuid.uuid4()
    prov = Provenance(source_type=ProvenanceSourceType.INTERNAL)
    await _save(
        database_url,
        SQLAlchemyUnpublishedStructureRepository,
        UnpublishedStructure(
            workspace_id=WS,
            protein_id=protein_id,
            provenance=prov,
            method="cryo-EM",
            resolution=2.4,
            ligands=(CompoundRef(compound_id=uuid.uuid4(), name="BDQ"),),
        ),
    )

    r = await client.get(f"/api/v1/proteins/{protein_id}/target-biology")
    assert r.status_code == 200
    body = r.json()
    assert len(body["unpublished_structure"]) == 1
    struct = body["unpublished_structure"][0]
    assert struct["method"] == "cryo-EM"
    assert struct["resolution"] == 2.4
    assert struct["ligands"][0]["name"] == "BDQ"
    assert body["protein_production"] == []


@pytest.mark.asyncio
async def test_empty_bundle_for_unknown_gene(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/genes/{uuid.uuid4()}/target-biology")
    assert r.status_code == 200
    assert r.json() == {
        "essentiality": [],
        "vulnerability": [],
        "hypomorph": [],
        "crispri_strain": [],
        "resistance_mutation": [],
    }


# --- Essentiality CRUD ------------------------------------------------------

_ESS_BODY = {
    "classification": "essential",
    "condition": "in vitro 7H9",
    "method": "TnSeq",
    "confidence": 0.98,
    "provenance": {"source_type": "published", "citations": [{"pmid": "28096490"}]},
}


@pytest.mark.asyncio
async def test_create_update_delete_essentiality(client: AsyncClient, database_url: str) -> None:
    gene_id = await _seed_gene(client, database_url)

    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality", json=_ESS_BODY
    )
    assert created.status_code == 201
    rec = created.json()
    assert rec["classification"] == "essential"
    assert rec["gene_id"] == str(gene_id)
    assert rec["provenance"]["citations"][0]["pmid"] == "28096490"
    record_id = rec["id"]

    # It shows up in the gene's bundle.
    bundle = (await client.get(f"/api/v1/genes/{gene_id}/target-biology")).json()
    assert [e["id"] for e in bundle["essentiality"]] == [record_id]

    # Update: change classification + method, drop the citation.
    updated = await client.patch(
        f"/api/v1/target-biology/essentiality/{record_id}",
        json={
            "classification": "non_essential",
            "method": "CRISPRi",
            "provenance": {"source_type": "internal", "citations": []},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["classification"] == "non_essential"
    assert updated.json()["method"] == "CRISPRi"
    assert updated.json()["provenance"]["citations"] == []

    # Delete → gone from the bundle.
    deleted = await client.delete(f"/api/v1/target-biology/essentiality/{record_id}")
    assert deleted.status_code == 204
    bundle2 = (await client.get(f"/api/v1/genes/{gene_id}/target-biology")).json()
    assert bundle2["essentiality"] == []


@pytest.mark.asyncio
async def test_update_missing_essentiality_404(client: AsyncClient) -> None:
    r = await client.patch(f"/api/v1/target-biology/essentiality/{uuid.uuid4()}", json=_ESS_BODY)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_essentiality_writes_require_admin(
    client: AsyncClient, editor_client: AsyncClient, database_url: str
) -> None:
    # A real, readable gene, seeded via the admin client — otherwise Task 10's
    # parent guard would 404 first and this would no longer be testing the
    # admin check at all. Seeding requires admin (organism create is
    # admin-gated too), which editor_client by definition is not.
    gene_id = await _seed_gene(client, database_url)
    r = await editor_client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality", json=_ESS_BODY
    )
    assert r.status_code == 403


async def test_patch_one_field_preserves_provenance_and_other_fields(
    client: AsyncClient, database_url: str, workspace_id: uuid.UUID
) -> None:
    """Editing `condition` must not touch provenance, generation_method, or siblings."""
    gene_id = uuid.uuid4()
    record = Essentiality(
        # Owned by the caller, not shared — a PATCH must find it via find_owned.
        # This test exercises patch-body semantics, not shared-row immutability
        # (see test_shared_essentiality_cannot_be_mutated in
        # test_workspace_isolation.py for that).
        workspace_id=workspace_id,
        gene_id=gene_id,
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(
            source_type=ProvenanceSourceType.PUBLISHED,
            generation_method=GenerationMethod.AI_EXTRACTED,
            citations=(Citation(pmid="28096490"), Citation(doi="10.1016/j.cell.2021.02.001")),
            contributor_researcher="A. Curator",
            observed_on=date(2021, 3, 1),
        ),
        condition="7H9",
        method="TnSeq",
        confidence=0.91,
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "cholesterol"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["condition"] == "cholesterol"
    # Untouched scalars survive.
    assert body["classification"] == "essential"
    assert body["method"] == "TnSeq"
    assert body["confidence"] == 0.91
    # Provenance survives in full — this is the regression this task exists for.
    prov = body["provenance"]
    assert prov["generation_method"] == "ai_extracted"
    assert len(prov["citations"]) == 2
    assert prov["citations"][1]["doi"] == "10.1016/j.cell.2021.02.001"
    assert prov["contributor_researcher"] == "A. Curator"
    assert prov["observed_on"] == "2021-03-01"


async def test_patch_with_provenance_reattributes_to_manual(
    client: AsyncClient, database_url: str, workspace_id: uuid.UUID
) -> None:
    """Submitting provenance is what re-attributes a record — and only that."""
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=workspace_id,  # owned by the caller — see the sibling test above
        gene_id=gene_id,
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(
            source_type=ProvenanceSourceType.PUBLISHED,
            generation_method=GenerationMethod.AI_EXTRACTED,
        ),
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"provenance": {"source_type": "internal", "citations": []}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provenance"]["generation_method"] == "manual"
    assert resp.json()["provenance"]["source_type"] == "internal"


async def test_patch_rejects_unknown_field(client: AsyncClient, database_url: str) -> None:
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=WS,
        gene_id=gene_id,
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"nonsense": 1},
    )
    assert resp.status_code == 422


async def test_patch_with_stale_version_conflicts(
    client: AsyncClient, database_url: str, workspace_id: uuid.UUID
) -> None:
    record = Essentiality(
        workspace_id=workspace_id,  # owned by the caller — see test_patch_one_field... above
        gene_id=uuid.uuid4(),
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
        condition="7H9",
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    first = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "cholesterol", "version": 1},
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 2

    # Someone else's browser still holds version 1.
    stale = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "glycerol", "version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["retry"] is True

    # The losing write must not have landed: a fresh read (via a correctly
    # versioned patch of an unrelated field) still shows the winner's value.
    recheck = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"method": "TnSeq", "version": 2},
    )
    assert recheck.status_code == 200, recheck.text
    assert recheck.json()["condition"] == "cholesterol"


async def test_patch_without_version_still_succeeds(
    client: AsyncClient, database_url: str, workspace_id: uuid.UUID
) -> None:
    """Version is opt-in — importers and scripts keep working."""
    record = Essentiality(
        workspace_id=workspace_id,  # owned by the caller — see test_patch_one_field... above
        gene_id=uuid.uuid4(),
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "7H9"},
    )
    assert resp.status_code == 200, resp.text


# --- Other record kinds through the generic CRUD path -----------------------

_INTERNAL_PROV = {"source_type": "internal", "citations": []}


@pytest.mark.asyncio
async def test_create_delete_vulnerability_gene_side(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = await _seed_gene(client, database_url)
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/vulnerability",
        json={"vulnerability_score": 0.86, "method": "CRISPRi-VI", "provenance": _INTERNAL_PROV},
    )
    assert created.status_code == 201
    rec = created.json()
    assert rec["vulnerability_score"] == 0.86
    record_id = rec["id"]

    bundle = (await client.get(f"/api/v1/genes/{gene_id}/target-biology")).json()
    assert [v["id"] for v in bundle["vulnerability"]] == [record_id]

    # Generic delete route, keyed by record kind.
    deleted = await client.delete(f"/api/v1/target-biology/vulnerability/{record_id}")
    assert deleted.status_code == 204
    bundle2 = (await client.get(f"/api/v1/genes/{gene_id}/target-biology")).json()
    assert bundle2["vulnerability"] == []


@pytest.mark.asyncio
async def test_create_protein_production_protein_side(
    client: AsyncClient, database_url: str
) -> None:
    protein_id = await _seed_protein(client, database_url)
    created = await client.post(
        f"/api/v1/proteins/{protein_id}/target-biology/protein_production",
        json={
            "status": "purified",
            "expression_host": "E. coli BL21",
            "provenance": _INTERNAL_PROV,
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "purified"

    bundle = (await client.get(f"/api/v1/proteins/{protein_id}/target-biology")).json()
    assert bundle["protein_production"][0]["expression_host"] == "E. coli BL21"


@pytest.mark.asyncio
async def test_hypomorph_severity_requires_growth_defect(
    client: AsyncClient, database_url: str
) -> None:
    # Domain invariant surfaces as a 4xx through the generic create path.
    gene_id = await _seed_gene(client, database_url)
    r = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/hypomorph",
        json={
            "growth_defect": False,
            "growth_defect_severity": "strong",
            "provenance": _INTERNAL_PROV,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_unknown_kind_is_422(client: AsyncClient) -> None:
    r = await client.delete(f"/api/v1/target-biology/not_a_kind/{uuid.uuid4()}")
    assert r.status_code == 422


# --- Previously-write-only fields: compound, ligands, knockdown_strain_id ---


async def test_resistance_mutation_compound_round_trips(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = await _seed_gene(client, database_url)
    compound_id = uuid.uuid4()

    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/resistance_mutation",
        json={
            "mutation": "S315T",
            "compound": {"compound_id": str(compound_id), "name": "isoniazid"},
            "mic_shift": 200,
            "provenance": {"source_type": "published", "citations": []},
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["compound"]["name"] == "isoniazid"
    assert created.json()["compound"]["compound_id"] == str(compound_id)

    record_id = created.json()["id"]
    other = uuid.uuid4()
    patched = await client.patch(
        f"/api/v1/target-biology/resistance_mutation/{record_id}",
        json={"compound": {"compound_id": str(other), "name": "rifampicin"}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["compound"]["name"] == "rifampicin"
    # An untouched compound survives a patch of something else.
    again = await client.patch(
        f"/api/v1/target-biology/resistance_mutation/{record_id}",
        json={"mic_shift": 64},
    )
    assert again.status_code == 200, again.text
    assert again.json()["compound"]["name"] == "rifampicin"


async def test_unpublished_structure_ligands_round_trip(
    client: AsyncClient, database_url: str
) -> None:
    protein_id = await _seed_protein(client, database_url)
    created = await client.post(
        f"/api/v1/proteins/{protein_id}/target-biology/unpublished_structure",
        json={
            "method": "X-ray",
            "resolution": 1.9,
            "ligands": [{"compound_id": str(uuid.uuid4()), "name": "ATP"}],
            "provenance": {"source_type": "internal", "citations": []},
        },
    )
    assert created.status_code == 201, created.text
    assert [lig["name"] for lig in created.json()["ligands"]] == ["ATP"]


async def test_hypomorph_knockdown_strain_round_trips(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = await _seed_gene(client, database_url)
    strain_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/hypomorph",
        json={
            "growth_defect": True,
            "growth_defect_severity": "severe",
            "knockdown_strain_id": str(strain_id),
            "provenance": {"source_type": "internal", "citations": []},
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["knockdown_strain_id"] == str(strain_id)


# --- Explicit null on PATCH --------------------------------------------------


async def test_patch_null_classification_is_422(client: AsyncClient, database_url: str) -> None:
    gene_id = await _seed_gene(client, database_url)
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality",
        json={"classification": "essential", "provenance": _INTERNAL_PROV},
    )
    assert created.status_code == 201, created.text
    r = await client.patch(
        f"/api/v1/target-biology/essentiality/{created.json()['id']}",
        json={"classification": None},
    )
    assert r.status_code == 422


async def test_patch_null_growth_defect_is_422(client: AsyncClient, database_url: str) -> None:
    gene_id = await _seed_gene(client, database_url)
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/hypomorph",
        json={"growth_defect": True, "provenance": _INTERNAL_PROV},
    )
    assert created.status_code == 201, created.text
    r = await client.patch(
        f"/api/v1/target-biology/hypomorph/{created.json()['id']}",
        json={"growth_defect": None},
    )
    assert r.status_code == 422


async def test_patch_null_clears_compound(client: AsyncClient, database_url: str) -> None:
    gene_id = await _seed_gene(client, database_url)
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/resistance_mutation",
        json={
            "mutation": "S315T",
            "compound": {"compound_id": str(uuid.uuid4()), "name": "isoniazid"},
            "provenance": _INTERNAL_PROV,
        },
    )
    assert created.status_code == 201, created.text
    r = await client.patch(
        f"/api/v1/target-biology/resistance_mutation/{created.json()['id']}",
        json={"compound": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["compound"] is None


async def test_patch_replaces_ligands(client: AsyncClient, database_url: str) -> None:
    protein_id = await _seed_protein(client, database_url)
    created = await client.post(
        f"/api/v1/proteins/{protein_id}/target-biology/unpublished_structure",
        json={
            "method": "X-ray",
            "ligands": [{"compound_id": str(uuid.uuid4()), "name": "ATP"}],
            "provenance": _INTERNAL_PROV,
        },
    )
    assert created.status_code == 201, created.text
    r = await client.patch(
        f"/api/v1/target-biology/unpublished_structure/{created.json()['id']}",
        json={"ligands": [{"compound_id": str(uuid.uuid4()), "name": "GTP"}]},
    )
    assert r.status_code == 200, r.text
    assert [lig["name"] for lig in r.json()["ligands"]] == ["GTP"]


# --- Published write contract ------------------------------------------------


async def test_schema_lists_every_kind_and_seeds_vocabulary(
    client: AsyncClient, database_url: str
) -> None:
    await _save(
        database_url,
        SQLAlchemyEssentialityRepository,
        Essentiality(
            workspace_id=WS,
            gene_id=uuid.uuid4(),
            classification=EssentialityClass.ESSENTIAL,
            provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
            condition="cholesterol",
        ),
    )

    resp = await client.get("/api/v1/target-biology/schema")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["kinds"]) == 8
    condition = next(
        f for f in body["kinds"]["essentiality"]["fields"] if f["name"] == "condition"
    )
    assert "cholesterol" in condition["suggested_values"]
    assert next(f["name"] for f in body["provenance"]["fields"]) == "source_type"


# --- Bulk list route (GET /target-biology/{kind}) ----------------------------


async def test_bulk_list_is_cursor_paginated_and_workspace_filtered(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = uuid.uuid4()
    prov = Provenance(source_type=ProvenanceSourceType.PUBLISHED)
    for condition in ("7H9", "cholesterol", "glycerol"):
        await _save(
            database_url,
            SQLAlchemyEssentialityRepository,
            Essentiality(
                workspace_id=WS,
                gene_id=gene_id,
                classification=EssentialityClass.ESSENTIAL,
                provenance=prov,
                condition=condition,
            ),
        )

    resp = await client.get(f"/api/v1/target-biology/essentiality?gene_id={gene_id}")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 3
    # WS is SHARED_WORKSPACE_ID — is_shared (Task 8) should come through unprompted.
    assert all(item["is_shared"] for item in items)


async def test_bulk_list_rejects_an_unknown_kind(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/target-biology/nonsense")
    assert resp.status_code == 422


async def test_bulk_list_walks_pages_via_cursor(client: AsyncClient, database_url: str) -> None:
    """limit=2 over 5 records must take 3 pages, visiting every record exactly once."""
    prov = Provenance(source_type=ProvenanceSourceType.INTERNAL)
    gene_ids = [uuid.uuid4() for _ in range(5)]
    for gid in gene_ids:
        await _save(
            database_url,
            SQLAlchemyEssentialityRepository,
            Essentiality(
                workspace_id=WS,
                gene_id=gid,
                classification=EssentialityClass.ESSENTIAL,
                provenance=prov,
            ),
        )
    gene_qs = "&".join(f"gene_id={gid}" for gid in gene_ids)

    seen: set[str] = set()
    cursor: str | None = None
    pages = 0
    while True:
        url = f"/api/v1/target-biology/essentiality?{gene_qs}&limit=2"
        if cursor is not None:
            url += f"&cursor={cursor}"
        resp = await client.get(url)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["items"]) <= 2
        seen.update(item["id"] for item in body["items"])
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
        assert pages < 10  # generous bound so a broken cursor can't hang the test

    assert pages == 3
    assert len(seen) == 5


async def _make_organism(client: AsyncClient, tax_id: int, name: str) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": tax_id, "rank": "species", "scientific_name": name},
    )
    if resp.status_code == 409:
        # Already created by an earlier test in this session — resolve instead.
        resolved = await client.get(f"/api/v1/organisms/resolve/{tax_id}")
        assert resolved.status_code == 200, resolved.text
        return resolved.json()["id"]
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _make_strain(client: AsyncClient, species_organism_id: str, name: str) -> str:
    resp = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_organism_id, "name": name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_bulk_list_filters_by_organism_and_strain(
    client: AsyncClient, database_url: str
) -> None:
    """organism_id/strain_id reach a target-biology record via a join to its
    gene (records carry no organism_id/strain_id of their own) — the risk
    surface this route adds beyond the existing gene_id/protein_id filters.
    """
    organism_id = await _make_organism(client, 941001, "Joinus testus")
    strain_id = await _make_strain(client, organism_id, "Strain J")

    gene_in_strain = Gene.create(
        workspace_id=WS,
        primary_name="geneInStrain",
        organism_id=uuid.UUID(organism_id),
        strain_id=uuid.UUID(strain_id),
    )
    gene_in_organism_only = Gene.create(
        workspace_id=WS, primary_name="geneInOrganismOnly", organism_id=uuid.UUID(organism_id)
    )
    await _save(database_url, SQLAlchemyGeneRepository, gene_in_strain)
    await _save(database_url, SQLAlchemyGeneRepository, gene_in_organism_only)

    prov = Provenance(source_type=ProvenanceSourceType.INTERNAL)
    await _save(
        database_url,
        SQLAlchemyEssentialityRepository,
        Essentiality(
            workspace_id=WS,
            gene_id=gene_in_strain.id,
            classification=EssentialityClass.ESSENTIAL,
            provenance=prov,
        ),
    )
    await _save(
        database_url,
        SQLAlchemyEssentialityRepository,
        Essentiality(
            workspace_id=WS,
            gene_id=gene_in_organism_only.id,
            classification=EssentialityClass.ESSENTIAL,
            provenance=prov,
        ),
    )

    by_organism = await client.get(
        f"/api/v1/target-biology/essentiality?organism_id={organism_id}"
    )
    assert by_organism.status_code == 200, by_organism.text
    assert {i["gene_id"] for i in by_organism.json()["items"]} == {
        str(gene_in_strain.id),
        str(gene_in_organism_only.id),
    }

    by_strain = await client.get(
        f"/api/v1/target-biology/essentiality?organism_id={organism_id}&strain_id={strain_id}"
    )
    assert by_strain.status_code == 200, by_strain.text
    assert {i["gene_id"] for i in by_strain.json()["items"]} == {str(gene_in_strain.id)}


async def test_bulk_list_covers_a_protein_side_kind(
    client: AsyncClient, database_url: str
) -> None:
    """The generic route also dispatches to the three protein-side repositories
    (parent=ProteinModel), not just the five gene-side ones exercised above.
    """
    protein_id = uuid.uuid4()
    await _save(
        database_url,
        SQLAlchemyProteinProductionRepository,
        ProteinProduction(
            workspace_id=WS,
            protein_id=protein_id,
            status="purified",
            provenance=Provenance(source_type=ProvenanceSourceType.INTERNAL),
        ),
    )

    resp = await client.get(f"/api/v1/target-biology/protein_production?protein_id={protein_id}")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "purified"
    assert items[0]["protein_id"] == str(protein_id)


async def test_bulk_list_rejects_a_filter_that_does_not_apply_to_the_kind(
    client: AsyncClient,
) -> None:
    """``essentiality`` is gene-parented — a ``protein_id`` filter would otherwise
    be silently dropped and the caller would get back the whole readable table,
    misread as scoped to that protein. Same the other way for a protein-parented
    kind and ``gene_id``.
    """
    gene_resp = await client.get(f"/api/v1/target-biology/essentiality?protein_id={uuid.uuid4()}")
    assert gene_resp.status_code == 422, gene_resp.text

    protein_resp = await client.get(
        f"/api/v1/target-biology/protein_production?gene_id={uuid.uuid4()}"
    )
    assert protein_resp.status_code == 422, protein_resp.text


async def test_schema_route_is_not_shadowed_by_the_bulk_list_route(client: AsyncClient) -> None:
    """Regression for route-registration order: /target-biology/{kind} must not
    be registered ahead of the literal /target-biology/schema path, or "schema"
    gets parsed as a (rejected) RecordKind and this 422s instead of 200ing.
    """
    resp = await client.get("/api/v1/target-biology/schema")
    assert resp.status_code == 200, resp.text
    assert "kinds" in resp.json()


# --- Parent validation on create (Task 10) -----------------------------------


async def test_create_rejects_a_gene_that_does_not_exist(client: AsyncClient) -> None:
    """A record must not be attachable to a UUID that has never existed."""
    resp = await client.post(
        f"/api/v1/genes/{uuid.uuid4()}/target-biology/essentiality",
        json={
            "classification": "essential",
            "provenance": {"source_type": "published", "citations": []},
        },
    )
    assert resp.status_code == 404, resp.text


async def test_create_rejects_a_protein_that_does_not_exist(client: AsyncClient) -> None:
    """Same guard, protein side — a distinct repository (SQLAlchemyProteinRepository,
    not SQLAlchemyGeneRepository) so the gene case above doesn't prove this one.
    """
    resp = await client.post(
        f"/api/v1/proteins/{uuid.uuid4()}/target-biology/protein_production",
        json={"status": "purified", "provenance": _INTERNAL_PROV},
    )
    assert resp.status_code == 404, resp.text
