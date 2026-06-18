"""Taxonomy repository protocols."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.taxonomy.organism import Organism


@runtime_checkable
class OrganismRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Organism | None: ...

    async def find_by_tax_id(self, tax_id: int) -> Organism | None: ...

    async def find_children(self, parent_id: uuid.UUID) -> list[Organism]: ...

    async def find_by_name(self, name: str) -> list[Organism]: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        rank: str | None = None,
    ) -> list[Organism]: ...

    async def save(self, aggregate: Organism) -> None: ...
