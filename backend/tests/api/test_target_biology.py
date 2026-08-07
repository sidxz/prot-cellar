"""API tests for the target-biology bundle read endpoints."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from protcellar.domain.target_biology.vulnerability import Vulnerability
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
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

WS = GLOBAL_WORKSPACE_ID


async def _save(database_url: str, repo_cls: type, aggregate: object) -> None:
    engine = create_async_engine(database_url)
    uow = AsyncUnitOfWork(async_sessionmaker(engine, expire_on_commit=False))
    async with uow:
        await repo_cls(uow).save(aggregate)  # type: ignore[operator]
        await uow.commit()
    await engine.dispose()


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
async def test_create_update_delete_essentiality(client: AsyncClient) -> None:
    gene_id = uuid.uuid4()

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
async def test_essentiality_writes_require_admin(editor_client: AsyncClient) -> None:
    gene_id = uuid.uuid4()
    r = await editor_client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality", json=_ESS_BODY
    )
    assert r.status_code == 403


async def test_patch_one_field_preserves_provenance_and_other_fields(
    client: AsyncClient, database_url: str
) -> None:
    """Editing `condition` must not touch provenance, generation_method, or siblings."""
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=WS,
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
    client: AsyncClient, database_url: str
) -> None:
    """Submitting provenance is what re-attributes a record — and only that."""
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=WS,
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


# --- Other record kinds through the generic CRUD path -----------------------

_INTERNAL_PROV = {"source_type": "internal", "citations": []}


@pytest.mark.asyncio
async def test_create_delete_vulnerability_gene_side(client: AsyncClient) -> None:
    gene_id = uuid.uuid4()
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
async def test_create_protein_production_protein_side(client: AsyncClient) -> None:
    protein_id = uuid.uuid4()
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
async def test_hypomorph_severity_requires_growth_defect(client: AsyncClient) -> None:
    # Domain invariant surfaces as a 4xx through the generic create path.
    r = await client.post(
        f"/api/v1/genes/{uuid.uuid4()}/target-biology/hypomorph",
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
