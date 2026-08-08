"""Unit tests for BulkUpsertCrispriStrain (in-memory fakes — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_crispri_strain import (
    BulkUpsertCrispriStrain,
    BulkUpsertCrispriStrainCommand,
    CrispriStrainImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self, genes: list[Gene]) -> None:
        self._genes = list(genes)

    async def list_by_organism(self, organism_id: uuid.UUID, *, batch: int = 1000) -> list[Gene]:
        return [g for g in self._genes if g.organism_id == organism_id]


class _FakeCsRepo:
    def __init__(self) -> None:
        self.items: list[CrispriStrain] = []

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, target_gene_id: uuid.UUID
    ) -> list[CrispriStrain]:
        return [
            s
            for s in self.items
            if s.target_gene_id == target_gene_id and s.workspace_id == workspace_id
        ]

    async def save(self, agg: CrispriStrain) -> None:
        for i, s in enumerate(self.items):
            if s.id == agg.id:
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


def _uc(gene_repo: _FakeGeneRepo, cs_repo: _FakeCsRepo) -> BulkUpsertCrispriStrain:
    return BulkUpsertCrispriStrain(_FakeUoW(), gene_repo, cs_repo, _NoopDispatcher())  # type: ignore[arg-type]


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


@pytest.mark.asyncio
async def test_creates_then_updates_by_name() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="rpoB", organism_id=org)
    cs_repo = _FakeCsRepo()
    uc = _uc(_FakeGeneRepo([gene]), cs_repo)
    cmd = BulkUpsertCrispriStrainCommand(
        organism_id=org,
        records=(CrispriStrainImportRecord(locus_key="rpoB", name="sgRNA-rpoB-1"),),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created"]
    assert cs_repo.items[0].name == "sgRNA-rpoB-1"
    assert cs_repo.items[0].target_gene_id == gene.id

    res2 = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res2] == ["updated"]
    assert len(cs_repo.items) == 1


@pytest.mark.asyncio
async def test_different_names_create_separate_strains() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="rpoB", organism_id=org)
    cs_repo = _FakeCsRepo()
    uc = _uc(_FakeGeneRepo([gene]), cs_repo)
    cmd = BulkUpsertCrispriStrainCommand(
        organism_id=org,
        records=(
            CrispriStrainImportRecord(locus_key="rpoB", name="strain-A"),
            CrispriStrainImportRecord(locus_key="rpoB", name="strain-B"),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created", "created"]
    assert len(cs_repo.items) == 2
