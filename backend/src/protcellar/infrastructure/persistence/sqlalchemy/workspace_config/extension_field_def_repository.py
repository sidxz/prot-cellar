"""SQLAlchemy repository for ExtensionFieldDef aggregates (registry).

``find_owned``, ``save``, and ``delete`` come from the shared
``SQLAlchemyRepository`` base (workspace-scoped CRUD + optimistic concurrency)
— only the extension-field-specific lookups are implemented here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import (
    SQLAlchemyRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_config.models import (
    ExtensionFieldDefModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import (
    owned_by,
    readable_by,
)


class SQLAlchemyExtensionFieldDefRepository(
    SQLAlchemyRepository[ExtensionFieldDef, ExtensionFieldDefModel]
):
    model_class = ExtensionFieldDefModel

    def _to_domain(self, model: ExtensionFieldDefModel) -> ExtensionFieldDef:
        return ExtensionFieldDef(
            id=model.id,
            workspace_id=model.workspace_id,
            kind=model.kind,
            name=model.name,
            label=model.label,
            field_type=ExtensionFieldType(model.field_type),
            options=model.options,
            position=model.position,
            show_in_table=model.show_in_table,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: ExtensionFieldDef) -> ExtensionFieldDefModel:
        return ExtensionFieldDefModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            kind=aggregate.kind,
            name=aggregate.name,
            label=aggregate.label,
            field_type=aggregate.field_type.value,
            options=aggregate.options,
            position=aggregate.position,
            show_in_table=aggregate.show_in_table,
            version=aggregate.version,
        )

    def _update_model(self, model: ExtensionFieldDefModel, aggregate: ExtensionFieldDef) -> None:
        # kind and name are immutable — deliberately not assigned here.
        model.label = aggregate.label
        model.field_type = aggregate.field_type.value
        model.options = aggregate.options
        model.position = aggregate.position
        model.show_in_table = aggregate.show_in_table

    async def list_for_kind(self, workspace_id: uuid.UUID, kind: str) -> list[ExtensionFieldDef]:
        stmt = (
            select(ExtensionFieldDefModel)
            .where(
                readable_by(ExtensionFieldDefModel, workspace_id),
                ExtensionFieldDefModel.kind == kind,
            )
            .order_by(ExtensionFieldDefModel.position, ExtensionFieldDefModel.name)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def list_all(self, workspace_id: uuid.UUID) -> list[ExtensionFieldDef]:
        stmt = (
            select(ExtensionFieldDefModel)
            .where(readable_by(ExtensionFieldDefModel, workspace_id))
            .order_by(
                ExtensionFieldDefModel.kind,
                ExtensionFieldDefModel.position,
                ExtensionFieldDefModel.name,
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def find_by_name(
        self, workspace_id: uuid.UUID, kind: str, name: str
    ) -> ExtensionFieldDef | None:
        # owned_by, not readable_by: this is the pre-create/pre-update duplicate
        # check against the (workspace_id, kind, name) unique index, mirroring
        # TagRepository.find_by_normalized — reference data (SHARED) never
        # declares extension fields, so this only ever guards a tenant's own rows.
        stmt = select(ExtensionFieldDefModel).where(
            owned_by(ExtensionFieldDefModel, workspace_id),
            ExtensionFieldDefModel.kind == kind,
            ExtensionFieldDefModel.name == name,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None
