"""GetProteome query — retrieve a single proteome reference record by ID."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.domain.taxonomy.repository import ProteomeRepository


@dataclass(frozen=True, kw_only=True)
class GetProteomeQuery(Query):
    proteome_id: uuid.UUID


class GetProteome:
    def __init__(self, uow: UnitOfWork, repo: ProteomeRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: GetProteomeQuery, auth: AuthContext | None = None
    ) -> Result[Proteome, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            proteome = await self._repo.find_by_id_in_workspace(
                GLOBAL_WORKSPACE_ID, input.proteome_id
            )
            if proteome is None:
                return Failure(NotFoundError("Proteome", str(input.proteome_id)))
            return Success(proteome)
