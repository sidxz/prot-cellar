"""Integration tests for the SQLAlchemy Gene repository (genomic-neighbor query)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.taxonomy.organism import Organism
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


@pytest.fixture
async def gene_uow(database_url: str, _run_migrations: None) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


async def _seed_organism(repo: SQLAlchemyOrganismRepository) -> uuid.UUID:
    organism = Organism.create(
        ncbi_tax_id=None, rank="species", scientific_name=f"Test organism {uuid.uuid4()}"
    )
    await repo.save(organism)
    return organism.id


@pytest.mark.asyncio
async def test_find_genomic_neighbors_returns_window_ordered(gene_uow: AsyncUnitOfWork) -> None:
    async with gene_uow as uow:
        organism_id = await _seed_organism(SQLAlchemyOrganismRepository(uow))
        gene_repo = SQLAlchemyGeneRepository(uow)
        for i, start in enumerate([100, 200, 300, 400, 500]):
            await gene_repo.save(
                Gene.create(
                    primary_name=f"g{i}",
                    organism_id=organism_id,
                    genomic_accession="NC_000962.3",
                    genomic_start=start,
                    genomic_end=start + 50,
                    genomic_strand="+",
                )
            )
        # A gene on a different replicon must never leak into the window.
        await gene_repo.save(
            Gene.create(
                primary_name="other",
                organism_id=organism_id,
                genomic_accession="NC_OTHER.1",
                genomic_start=300,
                genomic_end=350,
                genomic_strand="+",
            )
        )
        await uow.commit()

        out = await gene_repo.find_genomic_neighbors(
            organism_id=organism_id,
            genomic_accession="NC_000962.3",
            center_start=300,
            window=1,
        )

    assert [g.genomic_start for g in out] == [200, 300, 400]
    assert all(g.genomic_accession == "NC_000962.3" for g in out)


@pytest.mark.asyncio
async def test_find_genomic_neighbors_clamps_at_replicon_edges(gene_uow: AsyncUnitOfWork) -> None:
    async with gene_uow as uow:
        organism_id = await _seed_organism(SQLAlchemyOrganismRepository(uow))
        gene_repo = SQLAlchemyGeneRepository(uow)
        for i, start in enumerate([100, 200, 300]):
            await gene_repo.save(
                Gene.create(
                    primary_name=f"e{i}",
                    organism_id=organism_id,
                    genomic_accession="NC_000962.3",
                    genomic_start=start,
                    genomic_end=start + 50,
                )
            )
        await uow.commit()

        # Center on the first gene: no upstream neighbor, window downstream only.
        out = await gene_repo.find_genomic_neighbors(
            organism_id=organism_id,
            genomic_accession="NC_000962.3",
            center_start=100,
            window=5,
        )

    assert [g.genomic_start for g in out] == [100, 200, 300]
