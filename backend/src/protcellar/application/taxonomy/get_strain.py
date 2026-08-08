"""GetStrain query — retrieve a single strain by ID."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_same_workspace, require_workspace_role
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.taxonomy.repository import StrainRepository
from protcellar.domain.taxonomy.strain import Strain


@dataclass(frozen=True, kw_only=True)
class GetStrainQuery(Query):
    workspace_id: uuid.UUID
    strain_id: uuid.UUID


class GetStrain:
    def __init__(self, uow: UnitOfWork, repo: StrainRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: GetStrainQuery, auth: AuthContext | None = None
    ) -> Result[Strain, DomainError]:
        require_workspace_role(auth, "viewer")
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            strain = await self._repo.find_readable(input.workspace_id, input.strain_id)
            if strain is None:
                return Failure(NotFoundError("Strain", str(input.strain_id)))
            return Success(strain)
