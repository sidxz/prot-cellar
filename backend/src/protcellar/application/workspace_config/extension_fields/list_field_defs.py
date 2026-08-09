"""ListFieldDefs — read the extension-field registry for a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated, require_same_workspace
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.workspace_config.extension_fields.field_def import ExtensionFieldDef
from protcellar.domain.workspace_config.extension_fields.repository import (
    ExtensionFieldDefRepository,
)


@dataclass(frozen=True, kw_only=True)
class ListFieldDefsQuery(Query):
    workspace_id: uuid.UUID
    kind: str | None = None


class ListFieldDefs:
    def __init__(self, uow: UnitOfWork, repo: ExtensionFieldDefRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListFieldDefsQuery, auth: AuthContext | None = None
    ) -> Result[list[ExtensionFieldDef], DomainError]:
        require_authenticated(auth)
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            if input.kind is not None:
                field_defs = await self._repo.list_for_kind(input.workspace_id, input.kind)
            else:
                field_defs = await self._repo.list_all(input.workspace_id)
        return Success(field_defs)
