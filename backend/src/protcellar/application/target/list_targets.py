"""ListTargets query — retrieve all targets for a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_editor, require_same_workspace
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.target.enums import TargetType
from protcellar.domain.target.repository import TargetRepository
from protcellar.domain.target.target import Target


@dataclass(frozen=True, kw_only=True)
class ListTargetsQuery(Query):
    workspace_id: uuid.UUID
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    target_type: TargetType | None = None
    chembl_id: str | None = None
    component_protein_id: uuid.UUID | None = None
    organism_id: uuid.UUID | None = None
    tag_ids: tuple[uuid.UUID, ...] = ()
    match_all: bool = False


class ListTargets:
    def __init__(self, uow: UnitOfWork, repo: TargetRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListTargetsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[Target], DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            targets = await self._repo.find_by_workspace(
                input.workspace_id,
                cursor_id=input.cursor_id,
                limit=fetch_limit,
                target_type=input.target_type,
                chembl_id=input.chembl_id,
                component_protein_id=input.component_protein_id,
                organism_id=input.organism_id,
                tag_ids=list(input.tag_ids),
                match_all=input.match_all,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(targets) > effective_limit:
                targets = targets[:effective_limit]
                next_cursor = str(targets[-1].id)

            return Success(PageResult(items=targets, next_cursor=next_cursor))
