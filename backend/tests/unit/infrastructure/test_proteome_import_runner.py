"""Integration test for the proteome import runner — fake fetcher, real DB.

Exercises the whole pipeline (fetch → ensure organism + proteome → stream/map →
chunked BulkUpsertProteins → link membership) without touching the network, using
a function-scoped engine/UoW like ``test_proteome_membership``.

Each test uses distinct accessions / proteome id / tax id because the
function-scoped engine commits to the session-scoped container (no rollback),
so data persists across tests in the same run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.application.protein_catalog.bulk_upsert_proteins import BulkUpsertProteins
from protcellar.infrastructure.ingestion.import_runner import ProteomeImportRunner
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.proteome_repository import (
    SQLAlchemyProteomeRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from tests.fakes.fake_auth import FakeAuth


def _meta(proteome_id: str, tax_id: int) -> dict[str, Any]:
    return {
        "id": proteome_id,
        "taxonomy": {"taxonId": tax_id, "scientificName": "Importus testus"},
        "proteomeType": "Reference proteome",
        "modified": "2026-01-01",
    }


def _entries(acc1: str, acc2: str) -> list[dict[str, Any]]:
    return [
        {
            "primaryAccession": acc1,
            "uniProtkbId": "T1_TEST",
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQR", "molWeight": 1200, "crc64": "AAAA"},
            "organism": {"taxonId": 99970},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
            "features": [
                {"type": "Chain", "location": {"start": {"value": 1}, "end": {"value": 10}}}
            ],
        },
        {
            "primaryAccession": acc2,
            "uniProtkbId": "T2_TEST",
            "entryType": "UniProtKB unreviewed (TrEMBL)",
            "sequence": {"value": "MKTAYIAKQS", "molWeight": 1201, "crc64": "BBBB"},
            "organism": {"taxonId": 99970},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
        },
    ]


class _FakeClient:
    def __init__(self, meta: dict[str, Any], entries: list[dict[str, Any]]) -> None:
        self._meta = meta
        self._entries = entries

    async def fetch_proteome(self, proteome_id: str) -> dict[str, Any]:
        return self._meta

    async def iter_entries(self, proteome_id: str) -> AsyncIterator[dict[str, Any]]:
        for entry in self._entries:
            yield entry


class _NoopDispatcher:
    async def dispatch_all(self, events: Any) -> None:
        return None


@pytest.fixture
async def import_uow(
    database_url: str, _run_migrations: None
) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


def _runner(uow: AsyncUnitOfWork, meta: dict[str, Any], entries: list[dict[str, Any]]):
    protein_repo = SQLAlchemyProteinRepository(uow)
    bulk = BulkUpsertProteins(uow, protein_repo, _NoopDispatcher())  # type: ignore[arg-type]
    runner = ProteomeImportRunner(uow, _FakeClient(meta, entries), bulk, chunk_size=500)
    return runner, protein_repo


@pytest.mark.asyncio
async def test_import_creates_organism_proteome_proteins_and_membership(
    import_uow: AsyncUnitOfWork,
) -> None:
    runner, protein_repo = _runner(
        import_uow, _meta("UP000000099", 99970), _entries("P0DK01", "P0DK02")
    )

    summary = await runner.run("UP000000099", auth=FakeAuth(role="admin"))

    assert summary.entries == 2
    assert summary.created == 2
    assert summary.members_linked == 2

    async with import_uow:
        prepo = SQLAlchemyProteomeRepository(import_uow)
        proteome = await prepo.find_by_proteome_id("UP000000099")
        assert proteome is not None
        member_ids = await prepo.list_protein_ids(proteome.id)
        assert len(member_ids) == 2

        got = await protein_repo.find_by_accession("P0DK01")
        assert got is not None
        assert got.entry_name == "T1_TEST"
        assert len(got.features) == 1


@pytest.mark.asyncio
async def test_import_dry_run_persists_nothing(import_uow: AsyncUnitOfWork) -> None:
    runner, _ = _runner(import_uow, _meta("UP000000098", 99971), _entries("P0DK03", "P0DK04"))

    summary = await runner.run("UP000000098", dry_run=True, auth=FakeAuth(role="admin"))
    assert summary.entries == 2
    assert summary.created == 2
    assert summary.members_linked == 0

    async with import_uow:
        repo = SQLAlchemyProteinRepository(import_uow)
        assert await repo.find_by_accession("P0DK03") is None
