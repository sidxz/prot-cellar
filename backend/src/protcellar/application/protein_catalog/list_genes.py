"""ListGenes query — retrieve all gene reference nodes (paginated)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class ListGenesQuery(Query):
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    name: str | None = None
    organism_id: uuid.UUID | None = None


class ListGenes:
    def __init__(self, uow: UnitOfWork, repo: GeneRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListGenesQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[Gene], DomainError]:
        require_authenticated(auth)
        async with self._uow:
            if input.name is not None:
                # Name search — no cursor pagination
                genes = await self._repo.find_by_name(input.name, input.organism_id)
                return Success(PageResult(items=genes, next_cursor=None))

            # Paginated listing
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            genes = await self._repo.find_all(
                cursor_id=input.cursor_id,
                limit=fetch_limit,
                organism_id=input.organism_id,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(genes) > effective_limit:
                genes = genes[:effective_limit]
                next_cursor = str(genes[-1].id)

            return Success(PageResult(items=genes, next_cursor=next_cursor))
