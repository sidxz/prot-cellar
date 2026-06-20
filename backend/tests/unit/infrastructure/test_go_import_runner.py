"""Integration test for the GO import runner (injected parse + probe; real DB)."""

from __future__ import annotations

import io
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.infrastructure.ingestion.go_import_runner import GoImportRunner
from protcellar.infrastructure.ingestion.go_obo import read_obo
from protcellar.infrastructure.persistence.sqlalchemy.gene_ontology.go_ontology_repository import (
    SQLAlchemyGoOntologyRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

_FIXTURE = """format-version: 1.2
data-version: releases/2026-05-19
ontology: go

[Term]
id: GO:0090001
name: alpha
namespace: molecular_function
is_a: GO:0090002 ! beta

[Term]
id: GO:0090002
name: beta
namespace: molecular_function

[Term]
id: GO:0090003
name: gamma
namespace: molecular_function
is_obsolete: true
"""


@pytest.fixture
async def runner_uow(database_url: str, _run_migrations: None) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_go_import_runner_version_gate(runner_uow: AsyncUnitOfWork) -> None:
    runner = GoImportRunner(
        runner_uow,
        source_url="x",
        read_obo=lambda src: read_obo(io.StringIO(_FIXTURE)),
        probe_version=lambda src: "releases/2026-05-19",
    )

    first = await runner.run()
    assert first.terms_upserted == 3
    assert first.edges == 1
    assert first.skipped_unchanged is False

    # same release version -> no-op
    second = await runner.run()
    assert second.skipped_unchanged is True

    # --force re-runs
    third = await runner.run(force=True)
    assert third.skipped_unchanged is False

    async with runner_uow as uow:
        repo = SQLAlchemyGoOntologyRepository(uow)
        gamma = await repo.find_term("GO:0090003")
        assert gamma is not None and gamma.is_obsolete is True
        assert await repo.descendants("GO:0090002") == {"GO:0090001"}
