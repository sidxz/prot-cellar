"""Unit tests for BulkUpsertResistanceMutation (in-memory fakes — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_resistance_mutation import (
    BulkUpsertResistanceMutation,
    BulkUpsertResistanceMutationCommand,
    ResistanceMutationImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self, genes: list[Gene]) -> None:
        self._genes = list(genes)

    async def list_by_organism(self, organism_id: uuid.UUID, *, batch: int = 1000) -> list[Gene]:
        return [g for g in self._genes if g.organism_id == organism_id]


class _FakeRmRepo:
    def __init__(self) -> None:
        self.items: list[ResistanceMutation] = []

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[ResistanceMutation]:
        return [r for r in self.items if r.gene_id == gene_id and r.workspace_id == workspace_id]

    async def save(self, agg: ResistanceMutation) -> None:
        for i, r in enumerate(self.items):
            if r.id == agg.id:
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


def _uc(gene_repo: _FakeGeneRepo, rm_repo: _FakeRmRepo) -> BulkUpsertResistanceMutation:
    return BulkUpsertResistanceMutation(_FakeUoW(), gene_repo, rm_repo, _NoopDispatcher())  # type: ignore[arg-type]


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


@pytest.mark.asyncio
async def test_upsert_by_mutation_and_compound() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="katG", organism_id=org)
    rm_repo = _FakeRmRepo()
    uc = _uc(_FakeGeneRepo([gene]), rm_repo)
    c1, c2 = uuid.uuid4(), uuid.uuid4()

    # Same mutation, two different compounds -> two distinct records.
    cmd = BulkUpsertResistanceMutationCommand(
        organism_id=org,
        records=(
            ResistanceMutationImportRecord(locus_key="katG", mutation="S315T", compound_id=c1),
            ResistanceMutationImportRecord(locus_key="katG", mutation="S315T", compound_id=c2),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created", "created"]
    assert len(rm_repo.items) == 2

    # Re-run first row -> updated in place (same gene+mutation+compound).
    cmd2 = BulkUpsertResistanceMutationCommand(
        organism_id=org,
        records=(
            ResistanceMutationImportRecord(
                locus_key="katG", mutation="S315T", compound_id=c1, mic_shift=64.0
            ),
        ),
    )
    res2 = (await uc(cmd2, auth=_admin())).unwrap()
    assert res2[0].status == "updated"
    assert len(rm_repo.items) == 2


@pytest.mark.asyncio
async def test_empty_mutation_reported_failed() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="katG", organism_id=org)
    uc = _uc(_FakeGeneRepo([gene]), _FakeRmRepo())
    cmd = BulkUpsertResistanceMutationCommand(
        organism_id=org,
        records=(ResistanceMutationImportRecord(locus_key="katG", mutation="   "),),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert res[0].status == "failed"  # aggregate rejects empty mutation
