"""Integration test: cross_references persist as rows in protein_cross_references.

Uses a function-scoped engine/UoW (like test_proteome_membership) so the engine
lives in the test's own event loop.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.organism import Organism
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import (
    ProteinCrossReferenceModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


@pytest.fixture
async def xref_uow(database_url: str, _run_migrations: None) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_references_persist_as_rows(xref_uow: AsyncUnitOfWork) -> None:
    async with xref_uow as uow:
        org_repo = SQLAlchemyOrganismRepository(uow)
        protein_repo = SQLAlchemyProteinRepository(uow)
        org = Organism.create(
            workspace_id=SHARED_WORKSPACE_ID,
            ncbi_tax_id=99920,
            rank="species",
            scientific_name="Xref testus",
        )
        await org_repo.save(org)
        protein = Protein.create(
            primary_accession="P0DV01",
            organism_id=org.id,
            sequence="MKTAYIAKQR",
            is_reviewed=True,
            cross_references=[
                CrossReference(database="PDB", accession="1ABC", properties={"Method": "X-ray"}),
                CrossReference(database="GO", accession="GO:0003674"),
            ],
        )
        await protein_repo.save(protein)
        await uow.session.flush()

        rows = (
            (
                await uow.session.execute(
                    select(ProteinCrossReferenceModel).where(
                        ProteinCrossReferenceModel.protein_id == protein.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {r.database for r in rows} == {"PDB", "GO"}
        pdb = next(r for r in rows if r.database == "PDB")
        assert pdb.accession == "1ABC"
        assert pdb.properties == {"Method": "X-ray"}

        # and it round-trips back into the domain aggregate
        loaded = await protein_repo.find_by_accession("P0DV01")
        assert loaded is not None
        assert {x.database for x in loaded.cross_references} == {"PDB", "GO"}
