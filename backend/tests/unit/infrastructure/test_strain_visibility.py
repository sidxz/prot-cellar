"""Strain read-visibility: GLOBAL reference strains are shared across workspaces.

Strains imported as reference data live in ``SHARED_WORKSPACE_ID`` (like the
organisms/proteins/genes they accompany). Reads must surface those to every
workspace, while a workspace's own strains stay private and the strict
mutation path (``find_owned``) keeps GLOBAL strains read-only.

Uses the function-scoped real-DB ``uow`` fixture; commits persist to the
session container, so this test uses a unique tax id.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.strain import Strain
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.strain_repository import (
    SQLAlchemyStrainRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


@pytest.fixture
async def strain_uow(database_url: str, _run_migrations: None) -> AsyncIterator[AsyncUnitOfWork]:
    """Per-test engine/UoW (created in this test's event loop) to avoid the
    session-scoped engine's cross-loop teardown noise."""
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_global_strains_are_visible_to_any_workspace(strain_uow: AsyncUnitOfWork) -> None:
    uow = strain_uow
    workspace_a = uuid.uuid4()
    workspace_b = uuid.uuid4()

    # A species organism to anchor the strains to.
    async with uow:
        org_repo = SQLAlchemyOrganismRepository(uow)
        species = Organism.create(
            ncbi_tax_id=991773,
            rank="species",
            scientific_name="Visibilis testus",
            source=OrganismSource.LOCAL,
        )
        await org_repo.save(species)
        await uow.commit()
        species_id = species.id

    # One GLOBAL reference strain, one private tenant-A strain.
    async with uow:
        strain_repo = SQLAlchemyStrainRepository(uow)
        global_strain = Strain.create(
            workspace_id=SHARED_WORKSPACE_ID,
            species_organism_id=species_id,
            name="GLOBAL ref strain",
        )
        tenant_strain = Strain.create(
            workspace_id=workspace_a,
            species_organism_id=species_id,
            name="Tenant A strain",
        )
        await strain_repo.save(global_strain)
        await strain_repo.save(tenant_strain)
        await uow.commit()
        global_id = global_strain.id
        tenant_id = tenant_strain.id

    async with uow:
        repo = SQLAlchemyStrainRepository(uow)

        # Listing as workspace B surfaces the GLOBAL strain but not tenant A's.
        visible_ids = {s.id for s in await repo.find_by_workspace(workspace_b)}
        assert global_id in visible_ids
        assert tenant_id not in visible_ids

        # Get-by-id as workspace B: GLOBAL visible, another tenant's not.
        assert await repo.find_visible_by_id(workspace_b, global_id) is not None
        assert await repo.find_visible_by_id(workspace_b, tenant_id) is None

        # Mutation path stays strict — a tenant can't load the GLOBAL strain to edit it.
        assert await repo.find_owned(workspace_b, global_id) is None
