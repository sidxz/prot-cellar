"""GetProtein query — retrieve a single protein by UniProt accession."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.shared.errors import DomainError, NotFoundError


@dataclass(frozen=True, kw_only=True)
class GetProteinQuery(Query):
    accession: str


class GetProtein:
    def __init__(self, uow: UnitOfWork, repo: ProteinRepository) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: GetProteinQuery, auth: AuthContext | None = None
    ) -> Result[Protein, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            protein = await self._repo.find_by_accession(
                input.accession,
                workspace_id=auth.workspace_id,  # type: ignore[union-attr]
            )
            if protein is None:
                return Failure(NotFoundError("Protein", input.accession))
            return Success(protein)
