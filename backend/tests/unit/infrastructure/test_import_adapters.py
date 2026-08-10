"""Unit tests for the import adapter registry + wiring.

Tests:
1. Registry covers every ImportType and each adapter's .import_type matches its key.
2. ProteomeAdapter.run threads rt.reporter into the runner constructor.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from protcellar.domain.imports.enums import ImportType
from protcellar.infrastructure.ingestion.import_adapters import IMPORT_ADAPTERS


def test_every_import_type_has_an_adapter() -> None:
    assert set(IMPORT_ADAPTERS) == set(ImportType)
    for t, adapter in IMPORT_ADAPTERS.items():
        assert adapter.import_type is t


def test_natural_key_tolerates_a_missing_activity_measured() -> None:
    """activity_measured is optional; a sheet omitting it entirely must not crash the
    preview's collision check (a bare .strip() on None would)."""
    from protcellar.application.target_biology.bulk_upsert_protein_activity_assay import (
        ProteinActivityAssayImportRecord,
    )
    from protcellar.application.target_biology.crud import RecordKind
    from protcellar.infrastructure.ingestion.import_adapters import _natural_key

    rec = ProteinActivityAssayImportRecord(accession="P9WGE9", method="fluorescence")
    assert _natural_key(RecordKind.PROTEIN_ACTIVITY_ASSAY, rec) == (
        "P9WGE9",
        None,
        "fluorescence",
    )


def test_dispatch_order_runs_crispri_strain_before_hypomorph() -> None:
    """hypomorph resolves knockdown_strain against crispri_strain rows this
    same run may just have created — see _DISPATCH's own comment. A cheap,
    DB-free guard against that order silently drifting back."""
    from protcellar.application.target_biology.crud import RecordKind
    from protcellar.infrastructure.ingestion.import_adapters import _DISPATCH_ORDER

    assert _DISPATCH_ORDER[RecordKind.CRISPRI_STRAIN] < _DISPATCH_ORDER[RecordKind.HYPOMORPH]


@pytest.mark.asyncio
async def test_proteome_adapter_passes_reporter_to_runner(monkeypatch) -> None:
    captured: dict = {}

    class _StubRunner:
        def __init__(self, *args, reporter=None, **kwargs) -> None:
            captured["reporter"] = reporter

        async def run(self, *args, **kwargs):
            from protcellar.infrastructure.ingestion.import_runner import ImportSummary

            return ImportSummary(proteome_id="UP1", created=3)

    monkeypatch.setattr(
        "protcellar.infrastructure.ingestion.import_adapters.ProteomeImportRunner", _StubRunner
    )
    rt = _runtime(params={"proteome_id": "UP1", "force": False, "dry_run": True, "limit": None})
    summary = await IMPORT_ADAPTERS[ImportType.PROTEOME].run(rt)
    assert summary["created"] == 3
    assert captured["reporter"] is rt.reporter


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _runtime(*, params: dict):
    """Build a minimal ImportRuntime with stubs — no real DB or network."""
    from protcellar.application.imports.progress_reporter import NoopProgressReporter
    from protcellar.infrastructure.ingestion.import_adapters import ImportRuntime
    from tests.fakes.fake_auth import FakeAuth

    # Stub session_factory: returns a no-op context manager
    session_factory = MagicMock()

    # Stub dispatcher
    dispatcher = MagicMock()
    dispatcher.dispatch_all = AsyncMock(return_value=None)

    reporter = NoopProgressReporter()

    # Stub load_upload — should not be called in the proteome test
    async def _load_upload(ref: uuid.UUID) -> bytes:  # pragma: no cover
        return b""

    return ImportRuntime(
        session_factory=session_factory,
        dispatcher=dispatcher,
        reporter=reporter,
        params=params,
        auth=FakeAuth(role="admin"),
        load_upload=_load_upload,
        workspace_id=uuid.uuid4(),
    )
