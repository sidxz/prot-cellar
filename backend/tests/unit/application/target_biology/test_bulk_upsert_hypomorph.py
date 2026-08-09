"""Unit tests for BulkUpsertHypomorph (in-memory fakes — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_hypomorph import (
    BulkUpsertHypomorph,
    BulkUpsertHypomorphCommand,
    HypomorphImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.target_biology.hypomorph import Hypomorph
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self, genes: list[Gene]) -> None:
        self._genes = list(genes)

    async def list_by_organism(
        self, organism_id: uuid.UUID, *, workspace_id: uuid.UUID, batch: int = 1000
    ) -> list[Gene]:
        return [g for g in self._genes if g.organism_id == organism_id]


class _FakeHypRepo:
    def __init__(self) -> None:
        self.items: list[Hypomorph] = []

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Hypomorph]:
        return [h for h in self.items if h.gene_id == gene_id and h.workspace_id == workspace_id]

    async def save(self, agg: Hypomorph) -> None:
        for i, h in enumerate(self.items):
            if h.id == agg.id:
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


def _uc(gene_repo: _FakeGeneRepo, hyp_repo: _FakeHypRepo) -> BulkUpsertHypomorph:
    return BulkUpsertHypomorph(_FakeUoW(), gene_repo, hyp_repo, _NoopDispatcher())  # type: ignore[arg-type]


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


@pytest.mark.asyncio
async def test_creates_then_updates_idempotently() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)
    hyp_repo = _FakeHypRepo()
    uc = _uc(_FakeGeneRepo([gene]), hyp_repo)
    cmd = BulkUpsertHypomorphCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            HypomorphImportRecord(
                locus_key="Rv0667",
                growth_defect=True,
                growth_defect_severity="severe",
                method="CRISPRi",
            ),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created"]
    assert hyp_repo.items[0].growth_defect is True

    res2 = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res2] == ["updated"]
    assert len(hyp_repo.items) == 1


@pytest.mark.asyncio
async def test_severity_without_defect_reported_failed() -> None:
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)
    uc = _uc(_FakeGeneRepo([gene]), _FakeHypRepo())
    cmd = BulkUpsertHypomorphCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            HypomorphImportRecord(
                locus_key="Rv0667", growth_defect=False, growth_defect_severity="mild"
            ),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert res[0].status == "failed"  # aggregate: severity requires growth_defect
