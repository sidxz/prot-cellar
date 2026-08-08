"""ListOrganisms query — retrieve all organism reference nodes (paginated)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class ListOrganismsQuery(Query):
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    name: str | None = None
    rank: str | None = None
    tag_ids: tuple[uuid.UUID, ...] = ()
    match_all: bool = False


class ListOrganisms:
    def __init__(self, uow: UnitOfWork, repo: OrganismRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListOrganismsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[Organism], DomainError]:
        require_authenticated(auth)
        async with self._uow:
            if input.name is not None:
                # Name search — no cursor pagination
                organisms = await self._repo.find_by_name(
                    input.name,
                    workspace_id=auth.workspace_id,  # type: ignore[union-attr]
                )
                if input.rank is not None:
                    organisms = [o for o in organisms if o.rank == input.rank]
                return Success(PageResult(items=organisms, next_cursor=None))

            # Paginated listing
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            organisms = await self._repo.find_all(
                cursor_id=input.cursor_id,
                limit=fetch_limit,
                rank=input.rank,
                workspace_id=auth.workspace_id,  # type: ignore[union-attr]
                tag_ids=list(input.tag_ids),
                match_all=input.match_all,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(organisms) > effective_limit:
                organisms = organisms[:effective_limit]
                next_cursor = str(organisms[-1].id)

            return Success(PageResult(items=organisms, next_cursor=next_cursor))
