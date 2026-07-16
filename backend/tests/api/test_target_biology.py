"""API tests for the target-biology bundle read endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType
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
        Vulnerability(
            workspace_id=WS, gene_id=gene_id, provenance=prov, vulnerability_score=0.82
        ),
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
