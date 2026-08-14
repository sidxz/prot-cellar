"""Resolve an input identifier to the canonical protein (UUID, accession, or entry name)."""

from __future__ import annotations

import uuid
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
            workspace_id = auth.workspace_id  # type: ignore[union-attr]
            # A UUID is already canonical — look it up directly (the suite's cross-service
            # reads hold protein UUIDs, not accessions). Otherwise pivot through accession
            # (primary, then secondary), then entry name.
            try:
                protein_uuid = uuid.UUID(input.identifier)
            except ValueError:
                protein_uuid = None
            if protein_uuid is not None:
                protein = await self._repo.find_readable(workspace_id, protein_uuid)
                if protein is None:
                    return Failure(NotFoundError("Protein", input.identifier))
                return Success(protein)
            protein = await self._repo.find_by_accession(
                input.identifier, workspace_id=workspace_id
            )
            if protein is None:
                protein = await self._repo.find_by_entry_name(
                    input.identifier, workspace_id=workspace_id
                )
            if protein is None:
                return Failure(NotFoundError("Protein", input.identifier))
            return Success(protein)
