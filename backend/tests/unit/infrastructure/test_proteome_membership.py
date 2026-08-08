"""Integration test for proteome ↔ protein membership (proteome_proteins join).

Uses a function-scoped engine/UoW (built from the session-scoped ``database_url``)
so the engine lives in the test's own event loop — mirroring how ``api_app``
creates a per-test engine. The shared session-scoped ``uow`` fixture cannot be
used directly here because its engine is created in a different loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.proteome_repository import (
    SQLAlchemyProteomeRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


@pytest.fixture
async def membership_uow(
    database_url: str, _run_migrations: None
) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_proteome_protein_membership_is_idempotent(
    membership_uow: AsyncUnitOfWork,
) -> None:
    async with membership_uow as uow:
        org_repo = SQLAlchemyOrganismRepository(uow)
        proteome_repo = SQLAlchemyProteomeRepository(uow)
        protein_repo = SQLAlchemyProteinRepository(uow)

        org = Organism.create(
            workspace_id=SHARED_WORKSPACE_ID,
            ncbi_tax_id=99950,
            rank="species",
            scientific_name="Membership testus",
        )
        await org_repo.save(org)

        proteome = Proteome.create(
            workspace_id=SHARED_WORKSPACE_ID,
            uniprot_proteome_id="UP000077777",
            organism_id=org.id,
            proteome_type=ProteomeType.REFERENCE,
            is_reference=True,
        )
        await proteome_repo.save(proteome)

        p1 = Protein.create(
            primary_accession="P0DQ01", organism_id=org.id, sequence="MKTAYIAKQR", is_reviewed=True
        )
        p2 = Protein.create(
            primary_accession="P0DQ02", organism_id=org.id, sequence="MKTAYIAKQR", is_reviewed=True
        )
        await protein_repo.save(p1)
        await protein_repo.save(p2)
        await uow.session.flush()

        await proteome_repo.add_protein(proteome.id, p1.id)
        await proteome_repo.add_protein(proteome.id, p2.id)
        await proteome_repo.add_protein(proteome.id, p1.id)  # idempotent re-link

        ids = await proteome_repo.list_protein_ids(proteome.id)
        assert set(ids) == {p1.id, p2.id}
        assert len(ids) == 2  # no duplicate row from the idempotent re-add
