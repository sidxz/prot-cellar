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
    )
