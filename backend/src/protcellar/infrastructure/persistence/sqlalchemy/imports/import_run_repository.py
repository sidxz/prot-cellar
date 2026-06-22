"""SQLAlchemy ImportRun repository."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, tuple_

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.imports.repository import ImportRunRepository
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.imports.models import ImportRunModel


class SQLAlchemyImportRunRepository(
    SQLAlchemyRepository[ImportRun, ImportRunModel], ImportRunRepository
):
    model_class = ImportRunModel

    def _to_domain(self, model: ImportRunModel) -> ImportRun:
        return ImportRun(
            id=model.id,
            import_type=ImportType(model.import_type),
            params=dict(model.params) if model.params else {},
            target_key=model.target_key,
            requested_by=model.requested_by,
            status=ImportStatus(model.status),
            phase=model.phase,
            processed=model.processed,
            total=model.total,
            summary=dict(model.summary) if model.summary else {},
            source_version=model.source_version,
            error=model.error,
            upload_ref=model.upload_ref,
            started_at=model.started_at,  # type: ignore[arg-type]
            finished_at=model.finished_at,  # type: ignore[arg-type]
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: ImportRun) -> ImportRunModel:
        return ImportRunModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            import_type=aggregate.import_type.value,
            target_key=aggregate.target_key,
            status=aggregate.status.value,
            params=aggregate.params,
            summary=aggregate.summary,
            phase=aggregate.phase,
            processed=aggregate.processed,
            total=aggregate.total,
            source_version=aggregate.source_version,
            error=aggregate.error,
            requested_by=aggregate.requested_by,
            upload_ref=aggregate.upload_ref,
            started_at=aggregate.started_at,
            finished_at=aggregate.finished_at,
            version=aggregate.version,
        )

    def _update_model(self, model: ImportRunModel, aggregate: ImportRun) -> None:
        model.import_type = aggregate.import_type.value
        model.target_key = aggregate.target_key
        model.status = aggregate.status.value
        model.params = aggregate.params
        model.summary = aggregate.summary
        model.phase = aggregate.phase
        model.processed = aggregate.processed
        model.total = aggregate.total
        model.source_version = aggregate.source_version
        model.error = aggregate.error
        model.requested_by = aggregate.requested_by
        model.upload_ref = aggregate.upload_ref
        model.started_at = aggregate.started_at
        model.finished_at = aggregate.finished_at

    async def get(self, id: uuid.UUID) -> ImportRun | None:
        return await self.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, id)

    async def list(
        self, *, cursor: tuple[datetime, uuid.UUID] | None = None, limit: int = 50
    ) -> list[ImportRun]:
        stmt = select(ImportRunModel).order_by(
            ImportRunModel.created_at.desc(), ImportRunModel.id.desc()
        )
        if cursor is not None:  # cursor = (created_at, id)
            ts, cid = cursor
            stmt = stmt.where(tuple_(ImportRunModel.created_at, ImportRunModel.id) < (ts, cid))
        stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_active(self, import_type: ImportType, target_key: str) -> ImportRun | None:
        stmt = select(ImportRunModel).where(
            ImportRunModel.import_type == import_type.value,
            ImportRunModel.target_key == target_key,
            ImportRunModel.status.in_([ImportStatus.QUEUED.value, ImportStatus.RUNNING.value]),
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return self._to_domain_tracked(m) if m is not None else None
