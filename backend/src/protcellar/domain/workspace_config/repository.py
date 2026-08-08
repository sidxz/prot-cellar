"""Repository protocols for workspace configuration entities."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.workspace_config.organization import Organization


@runtime_checkable
class OrganizationRepository(Protocol):
    """Repository for Organization aggregates."""

    async def find_readable(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Organization | None: ...

    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Organization | None: ...

    async def save(self, aggregate: Organization) -> None: ...

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[Organization]: ...

    async def find_by_name(self, workspace_id: uuid.UUID, name: str) -> Organization | None: ...
