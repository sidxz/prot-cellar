"""Repository protocol for the extension-field-definition registry."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.workspace_config.extension_fields.field_def import ExtensionFieldDef


@runtime_checkable
class ExtensionFieldDefRepository(Protocol):
    async def list_for_kind(self, workspace_id: uuid.UUID, kind: str) -> list[ExtensionFieldDef]:
        """Definitions this workspace declared for one kind, ordered by position.

        ``readable_by``: a workspace sees its own declarations. Shared reference
        data carries no declarations of its own.
        """
        ...

    async def list_all(self, workspace_id: uuid.UUID) -> list[ExtensionFieldDef]: ...

    async def find_owned(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> ExtensionFieldDef | None: ...

    async def find_by_name(
        self, workspace_id: uuid.UUID, kind: str, name: str
    ) -> ExtensionFieldDef | None: ...

    async def save(self, aggregate: ExtensionFieldDef) -> None: ...

    async def delete(self, workspace_id: uuid.UUID, id: uuid.UUID) -> None: ...
