"""ListProteins query — retrieve protein reference records (paginated)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class ListProteinsQuery(Query):
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    organism_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    is_reviewed: bool | None = None
    min_length: int | None = None
    max_length: int | None = None


class ListProteins:
    def __init__(self, uow: UnitOfWork, repo: ProteinRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListProteinsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[Protein], DomainError]:
        require_authenticated(auth)
        async with self._uow:
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            proteins = await self._repo.find_all(
                cursor_id=input.cursor_id,
                limit=fetch_limit,
                organism_id=input.organism_id,
                gene_id=input.gene_id,
                is_reviewed=input.is_reviewed,
                min_length=input.min_length,
                max_length=input.max_length,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(proteins) > effective_limit:
                proteins = proteins[:effective_limit]
                next_cursor = str(proteins[-1].id)

            return Success(PageResult(items=proteins, next_cursor=next_cursor))
