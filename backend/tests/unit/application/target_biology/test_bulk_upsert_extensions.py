"""Unit tests for the ``extensions`` bag on bulk-upsert import records.

Merge semantics only — the bulk path stays unvalidated by design (no
``ExtensionValidator`` here; that lands on the workbook path in a later task).
Fixtures mirror ``test_bulk_upsert_vulnerability.py`` and
``test_bulk_upsert_essentiality.py``.
"""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentiality,
    BulkUpsertEssentialityCommand,
    EssentialityImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_vulnerability import (
    BulkUpsertVulnerability,
    BulkUpsertVulnerabilityCommand,
    VulnerabilityImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.vulnerability import Vulnerability
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self, genes: list[Gene]) -> None:
        self._genes = list(genes)

    async def list_by_organism(
        self, organism_id: uuid.UUID, *, workspace_id: uuid.UUID, batch: int = 1000
    ) -> list[Gene]:
        return [g for g in self._genes if g.organism_id == organism_id]


class _FakeVulnRepo:
    def __init__(self) -> None:
        self.items: list[Vulnerability] = []

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Vulnerability]:
        return [v for v in self.items if v.gene_id == gene_id and v.workspace_id == workspace_id]

    async def save(self, agg: Vulnerability) -> None:
        for i, v in enumerate(self.items):
            if v.id == agg.id:
                self.items[i] = agg
                return
        self.items.append(agg)


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


def _admin() -> FakeAuth:
    return FakeAuth(role="admin")


def _gene(org: uuid.UUID) -> Gene:
    return Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org)


@pytest.mark.asyncio
async def test_extensions_reach_the_created_record() -> None:
    """The registry declares these fields; without this the bulk path can never fill them."""
    org = uuid.uuid4()
    vuln_repo = _FakeVulnRepo()
    uc = BulkUpsertVulnerability(  # type: ignore[arg-type]
        _FakeUoW(), _FakeGeneRepo([_gene(org)]), vuln_repo, _NoopDispatcher()
    )
    cmd = BulkUpsertVulnerabilityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(VulnerabilityImportRecord(locus_key="Rv0667", extensions={"vi_bin": 3}),),
    )
    (await uc(cmd, auth=_admin())).unwrap()
    assert vuln_repo.items[0].extensions == {"vi_bin": 3}


@pytest.mark.asyncio
async def test_a_record_without_extensions_leaves_the_bag_alone_on_update() -> None:
    """An importer that does not mention extensions must not wipe values already stored —
    same rule the single-record PATCH path follows."""
    org = uuid.uuid4()
    vuln_repo = _FakeVulnRepo()
    uc = BulkUpsertVulnerability(  # type: ignore[arg-type]
        _FakeUoW(), _FakeGeneRepo([_gene(org)]), vuln_repo, _NoopDispatcher()
    )
    create_cmd = BulkUpsertVulnerabilityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            VulnerabilityImportRecord(
                locus_key="Rv0667", extensions={"legacy_key": "no import regenerates this"}
            ),
        ),
    )
    (await uc(create_cmd, auth=_admin())).unwrap()

    update_cmd = BulkUpsertVulnerabilityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(VulnerabilityImportRecord(locus_key="Rv0667", vulnerability_score=0.5),),
    )
    res = (await uc(update_cmd, auth=_admin())).unwrap()
    assert [r.status for r in res] == ["updated"]
    assert vuln_repo.items[0].vulnerability_score == 0.5
    assert vuln_repo.items[0].extensions == {"legacy_key": "no import regenerates this"}


@pytest.mark.asyncio
async def test_update_merges_new_extensions_over_stored_not_replaces() -> None:
    org = uuid.uuid4()
    vuln_repo = _FakeVulnRepo()
    uc = BulkUpsertVulnerability(  # type: ignore[arg-type]
        _FakeUoW(), _FakeGeneRepo([_gene(org)]), vuln_repo, _NoopDispatcher()
    )

    def _cmd(extensions: dict[str, object]) -> BulkUpsertVulnerabilityCommand:
        return BulkUpsertVulnerabilityCommand(
            target_workspace_id=SHARED_WORKSPACE_ID,
            organism_id=org,
            records=(VulnerabilityImportRecord(locus_key="Rv0667", extensions=extensions),),
        )

    (await uc(_cmd({"a": 1, "b": 2}), auth=_admin())).unwrap()
    (await uc(_cmd({"b": 20, "c": 3}), auth=_admin())).unwrap()

    assert vuln_repo.items[0].extensions == {"a": 1, "b": 20, "c": 3}


@pytest.mark.asyncio
async def test_essentiality_extensions_merge_over_the_helper_output_on_create() -> None:
    """bulk_upsert_essentiality writes its own raw_call/source_run_id via a local
    helper; the record's extensions must layer on top, not replace them."""
    org = uuid.uuid4()
    ess_repo = _FakeEssRepo()
    uc = BulkUpsertEssentiality(  # type: ignore[arg-type]
        _FakeUoW(), _FakeGeneRepo([_gene(org)]), ess_repo, _NoopDispatcher()
    )
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(
            EssentialityImportRecord(
                locus_key="Rv0667", classification="ES", extensions={"vi_bin": 3}
            ),
        ),
    )
    (await uc(cmd, auth=_admin())).unwrap()
    saved = ess_repo.items[0]
    assert saved.extensions["vi_bin"] == 3
    assert saved.extensions["raw_call"] == "ES"  # helper's own key still present


@pytest.mark.asyncio
async def test_essentiality_update_keeps_stored_extensions_the_helper_never_writes() -> None:
    """A value stored some other way (single-record PATCH, an earlier import) must
    survive an essentiality re-import whose record says nothing about extensions —
    the helper's unconditional write must not wholesale-replace the bag."""
    org = uuid.uuid4()
    ess_repo = _FakeEssRepo()
    uc = BulkUpsertEssentiality(  # type: ignore[arg-type]
        _FakeUoW(), _FakeGeneRepo([_gene(org)]), ess_repo, _NoopDispatcher()
    )
    cmd = BulkUpsertEssentialityCommand(
        target_workspace_id=SHARED_WORKSPACE_ID,
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="Rv0667", classification="ES"),),
    )
    (await uc(cmd, auth=_admin())).unwrap()
    ess_repo.items[0].extensions["reviewer_note"] = "flagged for follow-up"

    (await uc(cmd, auth=_admin())).unwrap()  # re-import, same call, no rec.extensions
    saved = ess_repo.items[0]
    assert saved.extensions["reviewer_note"] == "flagged for follow-up"
    assert saved.extensions["raw_call"] == "ES"
