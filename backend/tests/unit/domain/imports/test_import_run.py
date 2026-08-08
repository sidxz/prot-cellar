from __future__ import annotations

import uuid

import pytest

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.events import (
    ImportRunFailed,
    ImportRunQueued,
    ImportRunStarted,
    ImportRunSucceeded,
)
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.shared.errors import ConflictError

_WORKSPACE_ID = uuid.uuid4()


def _run() -> ImportRun:
    return ImportRun.create(
        workspace_id=_WORKSPACE_ID,
        import_type=ImportType.PROTEOME,
        params={"proteome_id": "UP000001584"},
        target_key="UP000001584",
        requested_by=uuid.uuid4(),
    )


def test_create_is_queued_in_the_callers_workspace_and_emits_queued() -> None:
    run = _run()
    assert run.status is ImportStatus.QUEUED
    assert run.workspace_id == _WORKSPACE_ID
    assert run.target_key == "UP000001584"
    events = run.collect_events()
    assert any(isinstance(e, ImportRunQueued) for e in events)
    assert events[0].aggregate_type == "ImportRun"


def test_lifecycle_start_progress_succeed() -> None:
    run = _run()
    run.clear_events()
    run.start()
    assert run.status is ImportStatus.RUNNING
    assert run.started_at is not None
    run.record_progress(phase="streaming entries", processed=500, total=4000)
    assert run.processed == 500 and run.total == 4000 and run.phase == "streaming entries"
    run.set_source_version("2026_02")
    run.succeed({"created": 10, "updated": 0, "skipped": 0, "failed": 0})
    assert run.status is ImportStatus.SUCCEEDED
    assert run.finished_at is not None
    assert run.summary["created"] == 10
    assert run.source_version == "2026_02"
    kinds = [type(e) for e in run.collect_events()]
    assert ImportRunStarted in kinds and ImportRunSucceeded in kinds


def test_progress_update_emits_no_event() -> None:
    run = _run()
    run.start()
    run.clear_events()
    run.record_progress(phase="x", processed=1, total=2)
    assert run.collect_events() == []


def test_fail_from_running_sets_error_and_event() -> None:
    run = _run()
    run.start()
    run.clear_events()
    run.fail("boom")
    assert run.status is ImportStatus.FAILED
    assert run.error == "boom"
    assert any(isinstance(e, ImportRunFailed) for e in run.collect_events())


def test_illegal_transition_start_when_not_queued() -> None:
    run = _run()
    run.start()
    with pytest.raises(ConflictError):
        run.start()


def test_succeed_requires_running() -> None:
    run = _run()  # still QUEUED
    with pytest.raises(ConflictError):
        run.succeed({})
