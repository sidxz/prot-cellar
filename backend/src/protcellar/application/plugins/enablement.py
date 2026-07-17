"""Workspace-scoped plugin enablement — repository port + use cases.

A plugin is *available* if it is in the code registry; it is *enabled* only if an
admin has turned it on for the workspace (opt-in). Runs are gated on enablement.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin, require_authenticated
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError


class WorkspacePluginRepository(Protocol):
    """Persistence port for the workspace↔plugin enablement association."""

    async def enabled_ids(self, workspace_id: uuid.UUID) -> set[str]: ...

    async def enable(
        self, workspace_id: uuid.UUID, plugin_id: str, enabled_by: uuid.UUID | None
    ) -> None: ...

    async def disable(self, workspace_id: uuid.UUID, plugin_id: str) -> None: ...


class ListEnabledPluginIds:
    """Query — the set of plugin ids enabled for the caller's workspace."""

    def __init__(self, uow: UnitOfWork, repo: WorkspacePluginRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(self, auth: AuthContext | None = None) -> set[str]:
        require_authenticated(auth)
        async with self._uow:
            return await self._repo.enabled_ids(auth.workspace_id)  # type: ignore[union-attr]


@dataclass(frozen=True, kw_only=True)
class SetPluginEnablementCommand:
    plugin_id: str
    enabled: bool


class SetPluginEnablement:
    """Command — an admin enables/disables a plugin for their workspace."""

    def __init__(self, uow: UnitOfWork, repo: WorkspacePluginRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, cmd: SetPluginEnablementCommand, auth: AuthContext | None = None
    ) -> Result[None, DomainError]:
        require_admin(auth)
        workspace_id: uuid.UUID = auth.workspace_id  # type: ignore[union-attr]
        async with self._uow:
            if cmd.enabled:
                await self._repo.enable(workspace_id, cmd.plugin_id, auth.user_id)  # type: ignore[union-attr]
            else:
                await self._repo.disable(workspace_id, cmd.plugin_id)
            await self._uow.commit()
        return Success(None)
