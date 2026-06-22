"""SQLAlchemy ImportUpload repository."""

from __future__ import annotations

import uuid

from protcellar.domain.imports.repository import ImportUploadRepository
from protcellar.domain.imports.upload import ImportUpload
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.imports.models import ImportUploadModel


class SQLAlchemyImportUploadRepository(
    SQLAlchemyRepository[ImportUpload, ImportUploadModel], ImportUploadRepository
):
    model_class = ImportUploadModel

    def _to_domain(self, model: ImportUploadModel) -> ImportUpload:
        return ImportUpload(
            id=model.id,
            filename=model.filename,
            content_type=model.content_type,
            data=bytes(model.data),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: ImportUpload) -> ImportUploadModel:
        return ImportUploadModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            filename=aggregate.filename,
            content_type=aggregate.content_type,
            data=aggregate.data,
            version=aggregate.version,
        )

    def _update_model(self, model: ImportUploadModel, aggregate: ImportUpload) -> None:
        model.filename = aggregate.filename
        model.content_type = aggregate.content_type
        model.data = aggregate.data

    async def get(self, id: uuid.UUID) -> ImportUpload | None:
        return await self.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, id)
