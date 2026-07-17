"""SQLAlchemy repository for workspace-scoped plugin enablement.

A thin association-table repo — not an aggregate repository — so it does direct
SELECT/INSERT/DELETE rather than extending :class:`SQLAlchemyRepository`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from protcellar.infrastructure.persistence.sqlalchemy.plugins.models import WorkspacePluginModel
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


class SQLAlchemyWorkspacePluginRepository:
    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def enabled_ids(self, workspace_id: uuid.UUID) -> set[str]:
        stmt = select(WorkspacePluginModel.plugin_id).where(
            WorkspacePluginModel.workspace_id == workspace_id
        )
        result = await self._session.execute(stmt)
        return set(result.scalars())

    async def enable(
        self, workspace_id: uuid.UUID, plugin_id: str, enabled_by: uuid.UUID | None
    ) -> None:
        # Idempotent: a second enable is a no-op (composite PK would otherwise conflict).
        existing = await self._session.get(WorkspacePluginModel, (workspace_id, plugin_id))
        if existing is None:
            self._session.add(
                WorkspacePluginModel(
                    workspace_id=workspace_id, plugin_id=plugin_id, enabled_by=enabled_by
                )
            )

    async def disable(self, workspace_id: uuid.UUID, plugin_id: str) -> None:
        await self._session.execute(
            delete(WorkspacePluginModel).where(
                WorkspacePluginModel.workspace_id == workspace_id,
                WorkspacePluginModel.plugin_id == plugin_id,
            )
        )
