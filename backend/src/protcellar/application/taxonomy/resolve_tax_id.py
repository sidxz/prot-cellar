"""Resolve an NCBI tax id to its live organism, following merge redirects."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, GoneError, NotFoundError
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class ResolveTaxIdQuery(Query):
    tax_id: int


class ResolveTaxId:
    def __init__(self, uow: UnitOfWork, repo: OrganismRepository) -> None:
        self._uow, self._repo = uow, repo

    async def __call__(
        self, input: ResolveTaxIdQuery, auth: AuthContext | None = None
    ) -> Result[Organism, DomainError]:
        async with self._uow:
            org = await self._repo.find_by_tax_id(input.tax_id)
            if org is None:
                return Failure(NotFoundError("Organism", str(input.tax_id)))
            if org.is_deleted:
                return Failure(GoneError(f"tax_id {input.tax_id} was deleted from NCBI Taxonomy"))
            if org.is_merged and org.merged_into_id is not None:
                target = await self._repo.find_by_id_in_workspace(
                    org.workspace_id, org.merged_into_id
                )
                if target is not None:
                    return Success(target)
            return Success(org)
