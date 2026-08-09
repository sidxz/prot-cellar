"""Unit tests for the hypomorph and unpublished-structure upsert keys (in-memory
fakes — no DB).

Both keys used to under-discriminate: hypomorph on (gene_id, condition, method)
and unpublished_structure on (protein_id, method), silently merging distinct
records that a real corpus actually holds. See the ``Upsert key is (...)``
docstring in each ``bulk_upsert_*.py`` module for the fixed key.
"""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_hypomorph import (
    BulkUpsertHypomorph,
    BulkUpsertHypomorphCommand,
    HypomorphImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_unpublished_structure import (
    BulkUpsertUnpublishedStructure,
    BulkUpsertUnpublishedStructureCommand,
    UnpublishedStructureImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from tests.fakes.fake_auth import FakeAuth

_ACC = "P9WGE9"


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


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


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


# ---------------------------------------------------------------------------
# Hypomorph fakes + helper
# ---------------------------------------------------------------------------


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


class _FakeCsRepo:
    def __init__(self, strains: list[CrispriStrain] | None = None) -> None:
        self.items: list[CrispriStrain] = list(strains or [])

    async def find_by_gene(
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


def _strain(gene_id: uuid.UUID, name: str) -> CrispriStrain:
    return CrispriStrain.create(
        workspace_id=SHARED_WORKSPACE_ID,
        name=name,
        target_gene_id=gene_id,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
    )


def _uc_hyp(
    gene_repo: _FakeGeneRepo, hyp_repo: _FakeHypRepo, cs_repo: _FakeCsRepo
) -> BulkUpsertHypomorph:
    return BulkUpsertHypomorph(  # type: ignore[arg-type]
        _FakeUoW(), gene_repo, hyp_repo, cs_repo, _NoopDispatcher()
    )


# ---------------------------------------------------------------------------
# UnpublishedStructure fakes + helper
# ---------------------------------------------------------------------------


class _FakeProteinRepo:
    def __init__(self, proteins: list[Protein]) -> None:
        self._by_acc = {p.primary_accession: p for p in proteins}

    async def find_by_accession(
        self, accession: str, *, workspace_id: uuid.UUID
    ) -> Protein | None:
        return self._by_acc.get(accession)


class _FakeStructRepo:
    def __init__(self) -> None:
        self.items: list[UnpublishedStructure] = []

    async def find_owned_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[UnpublishedStructure]:
        return [
            s for s in self.items if s.protein_id == protein_id and s.workspace_id == workspace_id
        ]

    async def save(self, agg: UnpublishedStructure) -> None:
        for i, s in enumerate(self.items):
            if s.id == agg.id:
                self.items[i] = agg
                return
        self.items.append(agg)


def _protein() -> Protein:
    return Protein.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_accession=_ACC,
        organism_id=uuid.uuid4(),
        sequence="MKALIV",
        is_reviewed=True,
    )


def _uc_struct(repo: _FakeStructRepo) -> BulkUpsertUnpublishedStructure:
    return BulkUpsertUnpublishedStructure(  # type: ignore[arg-type]
        _FakeUoW(), _FakeProteinRepo([_protein()]), repo, _NoopDispatcher()
    )


# ---------------------------------------------------------------------------
# hypomorph: (gene_id, knockdown_strain_id, condition, method)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_knockdown_strains_of_one_gene_are_two_hypomorphs() -> None:
    """A hypomorph IS a knockdown strain of a gene. Keyed without the strain, a real
    corpus collapsed 195 rows into 97."""
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)
    cs_repo = _FakeCsRepo([_strain(gene.id, "KD1"), _strain(gene.id, "KD2")])
    hyp_repo = _FakeHypRepo()
    uc = _uc_hyp(_FakeGeneRepo([gene]), hyp_repo, cs_repo)
    cmd = BulkUpsertHypomorphCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            HypomorphImportRecord(locus_key="Rv0667", growth_defect=True, knockdown_strain="KD1"),
            HypomorphImportRecord(locus_key="Rv0667", growth_defect=True, knockdown_strain="KD2"),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created", "created"]
    assert len(hyp_repo.items) == 2
    assert {h.knockdown_strain_id for h in hyp_repo.items} == {s.id for s in cs_repo.items}


@pytest.mark.asyncio
async def test_the_same_strain_twice_still_updates_rather_than_duplicating() -> None:
    """The key must still be a key."""
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)
    strain = _strain(gene.id, "KD1")
    hyp_repo = _FakeHypRepo()
    uc = _uc_hyp(_FakeGeneRepo([gene]), hyp_repo, _FakeCsRepo([strain]))

    def _cmd(severity: str | None) -> BulkUpsertHypomorphCommand:
        return BulkUpsertHypomorphCommand(
            target_workspace_id=SHARED_WORKSPACE_ID,
            organism_id=org,
            records=(
                HypomorphImportRecord(
                    locus_key="Rv0667",
                    growth_defect=True,
                    growth_defect_severity=severity,
                    knockdown_strain="KD1",
                ),
            ),
        )

    res1 = (await uc(_cmd("mild"), auth=_admin())).unwrap()
    assert [r.status for r in res1] == ["created"]

    res2 = (await uc(_cmd("severe"), auth=_admin())).unwrap()
    assert [r.status for r in res2] == ["updated"]
    assert len(hyp_repo.items) == 1
    assert hyp_repo.items[0].growth_defect_severity == "severe"
    assert hyp_repo.items[0].knockdown_strain_id == strain.id


@pytest.mark.asyncio
async def test_an_unresolvable_knockdown_strain_fails_its_row() -> None:
    """A strain name that matches nothing must not silently import strain-less —
    that would collide with (and merge into) another strain-less row for the same
    gene/condition/method, reintroducing the bug this key exists to prevent."""
    org = uuid.uuid4()
    gene = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)
    uc = _uc_hyp(_FakeGeneRepo([gene]), _FakeHypRepo(), _FakeCsRepo())
    cmd = BulkUpsertHypomorphCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            HypomorphImportRecord(
                locus_key="Rv0667", growth_defect=True, knockdown_strain="ghost-strain"
            ),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert res[0].status == "failed"
    assert "unmatched knockdown strain" in (res[0].error or "")


# ---------------------------------------------------------------------------
# unpublished_structure: (protein_id, method, ligands)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_ligand_bound_structures_of_one_protein_are_two_structures() -> None:
    """Keyed on (protein, method) alone, a real corpus collapsed 53 rows into 12 —
    one protein held thirteen X-ray structures differing only by ligand."""
    ligand_a, ligand_b = uuid.uuid4(), uuid.uuid4()
    repo = _FakeStructRepo()
    uc = _uc_struct(repo)
    cmd = BulkUpsertUnpublishedStructureCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        records=(
            UnpublishedStructureImportRecord(
                accession=_ACC, method="X-ray", ligand_ids=(ligand_a,)
            ),
            UnpublishedStructureImportRecord(
                accession=_ACC, method="X-ray", ligand_ids=(ligand_b,)
            ),
        ),
    )
    res = (await uc(cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["created", "created"]
    assert len(repo.items) == 2


@pytest.mark.asyncio
async def test_the_same_ligand_set_twice_still_updates_rather_than_duplicating() -> None:
    """The key must still be a key — and ligand order must not matter: [A, B] and
    [B, A] are the same structure."""
    ligand_a, ligand_b = uuid.uuid4(), uuid.uuid4()
    repo = _FakeStructRepo()
    uc = _uc_struct(repo)

    def _cmd(
        ligand_ids: tuple[uuid.UUID, ...], resolution: float
    ) -> BulkUpsertUnpublishedStructureCommand:
        return BulkUpsertUnpublishedStructureCommand(
            target_workspace_id=SHARED_WORKSPACE_ID,
            records=(
                UnpublishedStructureImportRecord(
                    accession=_ACC, method="X-ray", ligand_ids=ligand_ids, resolution=resolution
                ),
            ),
        )

    res1 = (await uc(_cmd((ligand_a, ligand_b), 1.8), auth=_admin())).unwrap()
    assert [r.status for r in res1] == ["created"]

    res2 = (await uc(_cmd((ligand_b, ligand_a), 1.5), auth=_admin())).unwrap()
    assert [r.status for r in res2] == ["updated"]
    assert len(repo.items) == 1
    assert repo.items[0].resolution == 1.5
