"""Pinned: every BulkUpsert*Command requires an explicit target_workspace_id.

No default. A silent SHARED fallback is exactly how the old hardcoding stayed
invisible across all eight target-biology bulk-import commands (see the
bulk_upsert_*.py modules in this package) — this file locks the property in
place so a future edit can't quietly reinstate it.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from returns.result import Success

from protcellar.application.target_biology.bulk_upsert_crispri_strain import (
    BulkUpsertCrispriStrainCommand,
    CrispriStrainImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentialityCommand,
    EssentialityImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_hypomorph import (
    BulkUpsertHypomorphCommand,
    HypomorphImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_protein_activity_assay import (
    BulkUpsertProteinActivityAssayCommand,
    ProteinActivityAssayImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_protein_production import (
    BulkUpsertProteinProductionCommand,
    ProteinProductionImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_resistance_mutation import (
    BulkUpsertResistanceMutationCommand,
    ResistanceMutationImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_unpublished_structure import (
    BulkUpsertUnpublishedStructureCommand,
    UnpublishedStructureImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_vulnerability import (
    BulkUpsertVulnerabilityCommand,
    VulnerabilityImportRecord,
)
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID

_ORG = uuid.uuid4()

# (command_cls, records, extra required kwargs besides target_workspace_id/records) —
# the 5 gene-side commands need organism_id, the 3 protein-side ones don't.
_CASES: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = [
    (
        BulkUpsertVulnerabilityCommand,
        (VulnerabilityImportRecord(locus_key="Rv0001"),),
        {"organism_id": _ORG},
    ),
    (
        BulkUpsertEssentialityCommand,
        (EssentialityImportRecord(locus_key="Rv0001", classification="ES"),),
        {"organism_id": _ORG},
    ),
    (
        BulkUpsertHypomorphCommand,
        (HypomorphImportRecord(locus_key="Rv0001", growth_defect=True),),
        {"organism_id": _ORG},
    ),
    (
        BulkUpsertCrispriStrainCommand,
        (CrispriStrainImportRecord(locus_key="Rv0001", name="sgRNA-1"),),
        {"organism_id": _ORG},
    ),
    (
        BulkUpsertResistanceMutationCommand,
        (ResistanceMutationImportRecord(locus_key="Rv0001", mutation="S315T"),),
        {"organism_id": _ORG},
    ),
    (
        BulkUpsertProteinProductionCommand,
        (ProteinProductionImportRecord(accession="P9WGE9", status="produced"),),
        {},
    ),
    (
        BulkUpsertProteinActivityAssayCommand,
        (ProteinActivityAssayImportRecord(accession="P9WGE9", activity_measured="ATPase"),),
        {},
    ),
    (
        BulkUpsertUnpublishedStructureCommand,
        (UnpublishedStructureImportRecord(accession="P9WGE9"),),
        {},
    ),
]


@pytest.mark.parametrize("command_cls,records,extra", _CASES)
def test_target_workspace_is_required_and_has_no_default(
    command_cls: Any, records: tuple[Any, ...], extra: dict[str, Any]
) -> None:
    """A silent SHARED default is how the old hardcoding stayed invisible."""
    with pytest.raises(TypeError):
        command_cls(records=records, **extra)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# The CLI importers pass SHARED explicitly. Both runners construct the command
# from raw kwargs with no test coverage before this, so pin the property
# directly against them rather than trusting a source read.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_imports_still_target_the_shared_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """These load public reference data. A tenant workspace here would hide it
    from everyone else.
    """
    from protcellar.scripts import _gene_import_cli

    captured: dict[str, Any] = {}

    class _StubCommand:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    class _StubUseCase:
        def __init__(self, *args: Any) -> None:
            pass

        async def __call__(self, command: Any, auth: Any) -> Success:
            return Success([])

    async def _fake_resolve(
        uow: object, *, organism_id: uuid.UUID | None, tax_id: int
    ) -> tuple[uuid.UUID, int]:
        return uuid.uuid4(), 1

    monkeypatch.setattr(_gene_import_cli, "resolve_organism_id", _fake_resolve)
    file = tmp_path / "in.tsv"
    file.write_text("locus\n", encoding="utf-8")

    await _gene_import_cli.run_gene_import(
        file=file,
        parse=lambda _text: [],
        command_cls=_StubCommand,
        use_case_cls=_StubUseCase,
        record_repo_cls=lambda uow: object(),
    )
    assert captured["target_workspace_id"] == SHARED_WORKSPACE_ID


@pytest.mark.asyncio
async def test_protein_cli_imports_still_target_the_shared_workspace(tmp_path: Path) -> None:
    """The protein-side CLI runner isn't in the plan's file list but shares the
    exact same property: it builds protein_production / protein_activity_assay /
    unpublished_structure commands and must also state SHARED explicitly.
    """
    from protcellar.scripts import _protein_import_cli

    captured: dict[str, Any] = {}

    class _StubCommand:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    class _StubUseCase:
        def __init__(self, *args: Any) -> None:
            pass

        async def __call__(self, command: Any, auth: Any) -> Success:
            return Success([])

    file = tmp_path / "in.tsv"
    file.write_text("accession\n", encoding="utf-8")

    await _protein_import_cli.run_protein_import(
        file=file,
        parse=lambda _text: [],
        command_cls=_StubCommand,
        use_case_cls=_StubUseCase,
        record_repo_cls=lambda uow: object(),
    )
    assert captured["target_workspace_id"] == SHARED_WORKSPACE_ID
