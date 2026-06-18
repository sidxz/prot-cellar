"""ListStrains query — retrieve all strains for a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_same_workspace, require_workspace_role
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.taxonomy.repository import StrainRepository
from protcellar.domain.taxonomy.strain import Strain


@dataclass(frozen=True, kw_only=True)
class ListStrainsQuery(Query):
    workspace_id: uuid.UUID
    cursor_id: uuid.UUID | None = None
    limit: int | None = None


class ListStrains:
    def __init__(self, uow: UnitOfWork, repo: StrainRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListStrainsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[Strain], DomainError]:
        require_workspace_role(auth, "viewer")
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            strains = await self._repo.find_by_workspace(
                input.workspace_id,
                cursor_id=input.cursor_id,
                limit=fetch_limit,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(strains) > effective_limit:
                strains = strains[:effective_limit]
                next_cursor = str(strains[-1].id)

            return Success(PageResult(items=strains, next_cursor=next_cursor))
