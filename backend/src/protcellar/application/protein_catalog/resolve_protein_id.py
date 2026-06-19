"""Resolve an input identifier to the canonical protein (accession or entry name)."""

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
class ResolveProteinIdQuery(Query):
    identifier: str


class ResolveProteinId:
    def __init__(self, uow: UnitOfWork, repo: ProteinRepository) -> None:
        self._uow, self._repo = uow, repo

    async def __call__(
        self, input: ResolveProteinIdQuery, auth: AuthContext | None = None
    ) -> Result[Protein, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            # Pivot through accession (primary, then secondary), then entry name.
            protein = await self._repo.find_by_accession(input.identifier)
            if protein is None:
                protein = await self._repo.find_by_entry_name(input.identifier)
            if protein is None:
                return Failure(NotFoundError("Protein", input.identifier))
            return Success(protein)
