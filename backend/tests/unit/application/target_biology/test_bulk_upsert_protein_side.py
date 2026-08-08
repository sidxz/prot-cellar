"""Unit tests for the protein-side bulk-upsert commands (in-memory fakes — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_protein_activity_assay import (
    BulkUpsertProteinActivityAssay,
    BulkUpsertProteinActivityAssayCommand,
    ProteinActivityAssayImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_protein_production import (
    BulkUpsertProteinProduction,
    BulkUpsertProteinProductionCommand,
    ProteinProductionImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_unpublished_structure import (
    BulkUpsertUnpublishedStructure,
    BulkUpsertUnpublishedStructureCommand,
    UnpublishedStructureImportRecord,
)
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from tests.fakes.fake_auth import FakeAuth

_ACC = "P9WGE9"


class _FakeProteinRepo:
    def __init__(self, proteins: list[Protein]) -> None:
        self._by_acc = {p.primary_accession: p for p in proteins}

    async def find_by_accession(self, accession: str) -> Protein | None:
        return self._by_acc.get(accession)


class _FakeRecordRepo:
    def __init__(self) -> None:
        self.items: list[object] = []

    async def find_by_protein(self, workspace_id: uuid.UUID, protein_id: uuid.UUID) -> list:
        return [
            r
            for r in self.items
            if r.protein_id == protein_id and r.workspace_id == workspace_id  # type: ignore[attr-defined]
        ]

    async def save(self, agg: object) -> None:
        for i, r in enumerate(self.items):
            if r.id == agg.id:  # type: ignore[attr-defined]
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


def _protein() -> Protein:
    return Protein.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_accession=_ACC,
        organism_id=uuid.uuid4(),
        sequence="MKALIV",
        is_reviewed=True,
    )


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


@pytest.mark.asyncio
async def test_production_create_then_update() -> None:
    repo = _FakeRecordRepo()
    uc = BulkUpsertProteinProduction(  # type: ignore[arg-type]
        _FakeUoW(), _FakeProteinRepo([_protein()]), repo, _NoopDispatcher()
    )
    cmd = BulkUpsertProteinProductionCommand(
        records=(
            ProteinProductionImportRecord(
                accession=_ACC, status="produced", expression_host="E. coli", method="IMAC"
            ),
        )
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created"]
    res2 = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res2] == ["updated"]
    assert len(repo.items) == 1


@pytest.mark.asyncio
async def test_production_unmatched_accession_failed() -> None:
    uc = BulkUpsertProteinProduction(  # type: ignore[arg-type]
        _FakeUoW(), _FakeProteinRepo([]), _FakeRecordRepo(), _NoopDispatcher()
    )
    cmd = BulkUpsertProteinProductionCommand(
        records=(ProteinProductionImportRecord(accession="Q00000", status="produced"),)
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert res[0].status == "failed"
    assert "unmatched accession" in (res[0].error or "")


@pytest.mark.asyncio
async def test_activity_assay_create_then_update() -> None:
    repo = _FakeRecordRepo()
    uc = BulkUpsertProteinActivityAssay(  # type: ignore[arg-type]
        _FakeUoW(), _FakeProteinRepo([_protein()]), repo, _NoopDispatcher()
    )
    cmd = BulkUpsertProteinActivityAssayCommand(
        records=(
            ProteinActivityAssayImportRecord(
                accession=_ACC, activity_measured="ATPase", method="fluorescence"
            ),
        )
    )
    assert [r.status for r in (await uc(cmd, auth=_admin())).unwrap()] == ["created"]
    assert [r.status for r in (await uc(cmd, auth=_admin())).unwrap()] == ["updated"]
    assert len(repo.items) == 1


@pytest.mark.asyncio
async def test_structure_ligands_and_bad_resolution() -> None:
    repo = _FakeRecordRepo()
    uc = BulkUpsertUnpublishedStructure(  # type: ignore[arg-type]
        _FakeUoW(), _FakeProteinRepo([_protein()]), repo, _NoopDispatcher()
    )
    ligand = uuid.uuid4()
    cmd = BulkUpsertUnpublishedStructureCommand(
        records=(
            UnpublishedStructureImportRecord(
                accession=_ACC, method="X-ray", resolution=1.9, ligand_ids=(ligand,)
            ),
            UnpublishedStructureImportRecord(accession=_ACC, method="cryo-EM", resolution=0.0),
        )
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert res[0].status == "created"
    assert res[1].status == "failed"  # resolution must be > 0
    assert repo.items[0].ligands[0].compound_id == ligand  # type: ignore[attr-defined]
