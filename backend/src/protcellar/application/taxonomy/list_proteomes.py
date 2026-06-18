"""ListProteomes query — retrieve all proteome reference records (paginated)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.domain.taxonomy.repository import ProteomeRepository


@dataclass(frozen=True, kw_only=True)
class ListProteomesQuery(Query):
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    organism_id: uuid.UUID | None = None


class ListProteomes:
    def __init__(self, uow: UnitOfWork, repo: ProteomeRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListProteomesQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[Proteome], DomainError]:
        require_authenticated(auth)
        async with self._uow:
            if input.organism_id is not None:
                proteomes = await self._repo.find_by_organism(input.organism_id)
                return Success(PageResult(items=proteomes, next_cursor=None))

            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            proteomes = await self._repo.find_all(
                cursor_id=input.cursor_id,
                limit=fetch_limit,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(proteomes) > effective_limit:
                proteomes = proteomes[:effective_limit]
                next_cursor = str(proteomes[-1].id)

            return Success(PageResult(items=proteomes, next_cursor=next_cursor))
