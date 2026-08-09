"""Unit tests for BulkUpsertEssentiality (in-memory fakes — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentiality,
    BulkUpsertEssentialityCommand,
    EssentialityImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import GenerationMethod
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self, genes: list[Gene]) -> None:
        self._genes = list(genes)

    async def list_by_organism(
        self, organism_id: uuid.UUID, *, workspace_id: uuid.UUID, batch: int = 1000
    ) -> list[Gene]:
        return [g for g in self._genes if g.organism_id == organism_id]


class _FakeEssRepo:
    def __init__(self) -> None:
        self.items: list[Essentiality] = []

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Essentiality]:
        return [e for e in self.items if e.gene_id == gene_id and e.workspace_id == workspace_id]

    async def save(self, agg: Essentiality) -> None:
        for i, e in enumerate(self.items):
            if e.id == agg.id:
                self.items[i] = agg
                return
        self.items.append(agg)


class _FakeUoW:
    async def commit(self) -> list:
        return []

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _NoopDispatcher:
    async def dispatch_all(self, events: object) -> None:
        return None


def _uc(gene_repo: _FakeGeneRepo, ess_repo: _FakeEssRepo) -> BulkUpsertEssentiality:
    return BulkUpsertEssentiality(_FakeUoW(), gene_repo, ess_repo, _NoopDispatcher())  # type: ignore[arg-type]


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


@pytest.mark.asyncio
async def test_creates_then_updates_idempotently() -> None:
    org = uuid.uuid4()
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org, synonyms=["rpoB"]
    )
    ess_repo = _FakeEssRepo()
    uc = _uc(_FakeGeneRepo([gene]), ess_repo)
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            EssentialityImportRecord(
                locus_key="rpoB", classification="ES", method="TnSeq", pmid="28096490"
            ),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created"]
    assert len(ess_repo.items) == 1
    assert ess_repo.items[0].classification is EssentialityClass.ESSENTIAL
    assert ess_repo.items[0].provenance.citations[0].pmid == "28096490"

    # Re-run: same gene + condition + method -> updated in place, no duplicate.
    res2 = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res2] == ["updated"]
    assert len(ess_repo.items) == 1


@pytest.mark.asyncio
async def test_unmatched_locus_is_reported_failed() -> None:
    org = uuid.uuid4()
    uc = _uc(_FakeGeneRepo([]), _FakeEssRepo())
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="NOPE", classification="ES"),),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert res[0].status == "failed"
    assert "unmatched" in (res[0].error or "")


@pytest.mark.asyncio
async def test_dry_run_writes_nothing() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)
    ess_repo = _FakeEssRepo()
    uc = _uc(_FakeGeneRepo([gene]), ess_repo)
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="Rv0667", classification="NE"),),
        dry_run=True,
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created"]
    assert ess_repo.items == []  # nothing persisted on dry run


@pytest.mark.asyncio
async def test_default_generation_method_is_imported() -> None:
    org = uuid.uuid4()
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org, synonyms=["rpoB"]
    )
    ess_repo = _FakeEssRepo()
    uc = _uc(_FakeGeneRepo([gene]), ess_repo)
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="rpoB", classification="ES"),),
    )
    (await uc(cmd, auth=_admin())).unwrap()
    assert ess_repo.items[0].provenance.generation_method is GenerationMethod.IMPORTED


@pytest.mark.asyncio
async def test_stamps_generation_method_and_source_run_id() -> None:
    org = uuid.uuid4()
    run_id = uuid.uuid4()
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org, synonyms=["rpoB"]
    )
    ess_repo = _FakeEssRepo()
    uc = _uc(_FakeGeneRepo([gene]), ess_repo)
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="rpoB", classification="ES"),),
        generation_method=GenerationMethod.AI_EXTRACTED.value,
        source_run_id=run_id,
    )
    (await uc(cmd, auth=_admin())).unwrap()
    saved = ess_repo.items[0]
    assert saved.provenance.generation_method is GenerationMethod.AI_EXTRACTED
    assert saved.extensions["source_run_id"] == str(run_id)
    assert saved.extensions["raw_call"] == "ES"
