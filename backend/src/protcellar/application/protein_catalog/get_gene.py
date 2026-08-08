"""GetGene query — retrieve a single gene reference node by ID."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError, NotFoundError


@dataclass(frozen=True, kw_only=True)
class GetGeneQuery(Query):
    gene_id: uuid.UUID


class GetGene:
    def __init__(self, uow: UnitOfWork, repo: GeneRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: GetGeneQuery, auth: AuthContext | None = None
    ) -> Result[Gene, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            gene = await self._repo.find_readable(
                auth.workspace_id,  # type: ignore[union-attr]
                input.gene_id,
            )
            if gene is None:
                return Failure(NotFoundError("Gene", str(input.gene_id)))
            return Success(gene)
