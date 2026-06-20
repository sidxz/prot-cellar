"""Integration test for the GO ontology repository (bulk upsert + version)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.domain.gene_ontology.go_term import GoEdge, GoTerm
from protcellar.infrastructure.persistence.sqlalchemy.gene_ontology.go_ontology_repository import (
    SQLAlchemyGoOntologyRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


@pytest.fixture
async def go_uow(database_url: str, _run_migrations: None) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_upsert_terms_replace_edges_and_version(go_uow: AsyncUnitOfWork) -> None:
    async with go_uow as uow:
        repo = SQLAlchemyGoOntologyRepository(uow)
        await repo.upsert_terms(
            [
                GoTerm(
                    go_id="GO:0016491",
                    name="oxidoreductase activity",
                    namespace="molecular_function",
                ),
                GoTerm(
                    go_id="GO:0003674", name="molecular_function", namespace="molecular_function"
                ),
            ],
            source_version="releases/2026-05-19",
        )
        await repo.replace_edges(
            [GoEdge(child_go_id="GO:0016491", parent_go_id="GO:0003674", relation="is_a")]
        )

        term = await repo.find_term("GO:0016491")
        assert term is not None
        assert term.namespace == "molecular_function"
        assert await repo.find_term("GO:9999999") is None
        assert await repo.latest_source_version() == "releases/2026-05-19"

        # idempotent: re-upsert the same go_id with a changed name updates in place
        await repo.upsert_terms(
            [GoTerm(go_id="GO:0016491", name="renamed", namespace="molecular_function")],
            source_version="releases/2026-06-01",
        )
        updated = await repo.find_term("GO:0016491")
        assert updated is not None
        assert updated.name == "renamed"
