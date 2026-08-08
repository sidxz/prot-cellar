from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.events import (
    ImportRunFailed,
    ImportRunQueued,
    ImportRunStarted,
    ImportRunSucceeded,
)
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ConflictError

_AGG = "ImportRun"


class ImportRun(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        import_type: ImportType,
        params: dict[str, Any] | None = None,
        target_key: str,
        requested_by: uuid.UUID,
        status: ImportStatus = ImportStatus.QUEUED,
        phase: str | None = None,
        processed: int | None = None,
        total: int | None = None,
        summary: dict[str, Any] | None = None,
        source_version: str | None = None,
        error: str | None = None,
        upload_ref: uuid.UUID | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = workspace_id
        self.import_type = import_type
        self.params = params or {}
        self.target_key = target_key
        self.requested_by = requested_by
        self.status = status
        self.phase = phase
        self.processed = processed
        self.total = total
        self.summary = summary or {}
        self.source_version = source_version
        self.error = error
        self.upload_ref = upload_ref
        self.started_at = started_at
        self.finished_at = finished_at

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        import_type: ImportType,
        params: dict[str, Any],
        target_key: str,
        requested_by: uuid.UUID,
        upload_ref: uuid.UUID | None = None,
    ) -> ImportRun:
        run = cls(
            workspace_id=workspace_id,
            import_type=import_type,
            params=params,
            target_key=target_key,
            requested_by=requested_by,
            upload_ref=upload_ref,
        )
        run.register_event(
            ImportRunQueued(
                aggregate_id=run.id,
                aggregate_type=_AGG,
                workspace_id=run.workspace_id,
                import_type=import_type,
            )
        )
        return run

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)

    def start(self) -> None:
        if self.status is not ImportStatus.QUEUED:
            raise ConflictError(f"Cannot start import in status '{self.status}'")
        self.status = ImportStatus.RUNNING
        self.started_at = datetime.now(UTC)
        self._touch()
        self.register_event(
            ImportRunStarted(
                aggregate_id=self.id, aggregate_type=_AGG, workspace_id=self.workspace_id
            )
        )

    def record_progress(
        self, *, phase: str | None = None, processed: int | None = None, total: int | None = None
    ) -> None:
        if phase is not None:
            self.phase = phase
        if processed is not None:
            self.processed = processed
        if total is not None:
            self.total = total
        self._touch()

    def set_source_version(self, version: str | None) -> None:
        self.source_version = version
        self._touch()

    def record_summary(self, summary: dict[str, Any]) -> None:
        self.summary = dict(summary)
        self._touch()

    def succeed(self, summary: dict[str, Any]) -> None:
        if self.status is not ImportStatus.RUNNING:
            raise ConflictError(f"Cannot succeed import in status '{self.status}'")
        self.status = ImportStatus.SUCCEEDED
        self.summary = dict(summary)
        self.finished_at = datetime.now(UTC)
        self._touch()
        self.register_event(
            ImportRunSucceeded(
                aggregate_id=self.id, aggregate_type=_AGG, workspace_id=self.workspace_id
            )
        )

    def fail(self, error: str) -> None:
        if self.status in (ImportStatus.SUCCEEDED, ImportStatus.FAILED, ImportStatus.CANCELLED):
            raise ConflictError(f"Cannot fail import in terminal status '{self.status}'")
        self.status = ImportStatus.FAILED
        self.error = error
        self.finished_at = datetime.now(UTC)
        self._touch()
        self.register_event(
            ImportRunFailed(
                aggregate_id=self.id,
                aggregate_type=_AGG,
                workspace_id=self.workspace_id,
                error=error,
            )
        )
