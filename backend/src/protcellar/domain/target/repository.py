"""Target repository protocol."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.target.enums import TargetType
from protcellar.domain.target.target import Target


@runtime_checkable
class TargetRepository(Protocol):
    async def find_readable(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Target | None: ...

    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> Target | None: ...

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        target_type: TargetType | None = None,
        chembl_id: str | None = None,
        component_protein_id: uuid.UUID | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        match_all: bool = False,
    ) -> list[Target]: ...

    async def save(self, aggregate: Target) -> None: ...
