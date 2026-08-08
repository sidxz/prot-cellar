"""GetOrganism query — retrieve a single organism reference node by ID."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class GetOrganismQuery(Query):
    organism_id: uuid.UUID


class GetOrganism:
    def __init__(self, uow: UnitOfWork, repo: OrganismRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: GetOrganismQuery, auth: AuthContext | None = None
    ) -> Result[Organism, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            org = await self._repo.find_readable(
                auth.workspace_id,  # type: ignore[union-attr]
                input.organism_id,
            )
            if org is None:
                return Failure(NotFoundError("Organism", str(input.organism_id)))
            return Success(org)
