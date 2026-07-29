"""Unit tests for BulkUpsertGenes (in-memory fake repo — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenes,
    BulkUpsertGenesCommand,
    GeneImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self) -> None:
        self.by_srid: dict[tuple[str, str], Gene] = {}

    async def find_by_source_record_id(self, source: str, source_record_id: str) -> Gene | None:
        return self.by_srid.get((source, source_record_id))

    async def save(self, gene: Gene) -> None:
        self.by_srid[(gene.source, gene.source_record_id)] = gene


class _FakeUoW:
    @property
    def is_active(self) -> bool:
        return True

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


def _rec(
    srid: str = "83332:Rv1908c",
    checksum: str = "c1",
    primary: str = "katG",
    ordered_locus_names: tuple[str, ...] = ("Rv1908c",),
) -> GeneImportRecord:
    return GeneImportRecord(
        primary_name=primary,
        organism_id=uuid.uuid4(),
        source="uniprot",
        source_release="2026_02",
        source_record_id=srid,
        source_record_checksum=checksum,
        synonyms=(),
        ordered_locus_names=ordered_locus_names,
    )


def _uc(repo: _FakeGeneRepo) -> BulkUpsertGenes:
    return BulkUpsertGenes(_FakeUoW(), repo, _NoopDispatcher())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_creates_then_skips_then_updates() -> None:
    repo = _FakeGeneRepo()
    uc = _uc(repo)
    auth = FakeAuth(role="admin")

    r1 = (await uc(BulkUpsertGenesCommand(records=(_rec(),)), auth=auth)).unwrap()
    assert [x.status for x in r1] == ["created"]

    r2 = (await uc(BulkUpsertGenesCommand(records=(_rec(),)), auth=auth)).unwrap()
    assert [x.status for x in r2] == ["skipped"]

    r3 = (
        await uc(
            BulkUpsertGenesCommand(records=(_rec(checksum="c2", primary="katG2"),)), auth=auth
        )
    ).unwrap()
    assert [x.status for x in r3] == ["updated"]
    assert repo.by_srid[("uniprot", "83332:Rv1908c")].primary_name == "katG2"


@pytest.mark.asyncio
async def test_update_without_strain_preserves_existing_strain() -> None:
    # A strain-scoped gene must keep its strain when a later upsert (e.g. the
    # /genes/bulk route) omits strain_id — the update must not null it out.
    repo = _FakeGeneRepo()
    uc = _uc(repo)
    auth = FakeAuth(role="admin")
    strain = uuid.uuid4()

    strain_rec = GeneImportRecord(
        primary_name="katG",
        organism_id=uuid.uuid4(),
        source="uniprot",
        source_release="2026_02",
        source_record_id="83332:Rv1908c",
        source_record_checksum="c1",
        strain_id=strain,
    )
    (await uc(BulkUpsertGenesCommand(records=(strain_rec,)), auth=auth)).unwrap()
    assert repo.by_srid[("uniprot", "83332:Rv1908c")].strain_id == strain

    # Re-upsert with a changed checksum but NO strain_id (default None on _rec).
    r = (
        await uc(
            BulkUpsertGenesCommand(records=(_rec(checksum="c2", primary="katG2"),)), auth=auth
        )
    ).unwrap()
    assert [x.status for x in r] == ["updated"]
    gene = repo.by_srid[("uniprot", "83332:Rv1908c")]
    assert gene.primary_name == "katG2"
    assert gene.strain_id == strain  # preserved, not nulled


@pytest.mark.asyncio
async def test_dry_run_persists_nothing() -> None:
    repo = _FakeGeneRepo()
    r = (
        await _uc(repo)(
            BulkUpsertGenesCommand(records=(_rec(),), dry_run=True), auth=FakeAuth(role="admin")
        )
    ).unwrap()
    assert [x.status for x in r] == ["created"]
    assert repo.by_srid == {}


@pytest.mark.asyncio
async def test_created_gene_carries_ordered_locus_names() -> None:
    repo = _FakeGeneRepo()
    uc = _uc(repo)
    auth = FakeAuth(role="admin")
    await uc(BulkUpsertGenesCommand(records=(_rec(),)), auth=auth)
    saved = repo.by_srid[("uniprot", "83332:Rv1908c")]
    assert saved.ordered_locus_names == ["Rv1908c"]
