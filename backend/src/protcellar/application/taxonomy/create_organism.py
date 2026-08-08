"""Create an organism reference node (admin/service only)."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import ConflictError, DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class CreateOrganismCommand(Command):
    ncbi_tax_id: int | None
    rank: str
    scientific_name: str
    source: OrganismSource = OrganismSource.NCBI
    division: str | None = None
    source_version: str | None = None


class CreateOrganism:
    def __init__(
        self, uow: UnitOfWork, repo: OrganismRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateOrganismCommand, auth: AuthContext | None = None
    ) -> Result[Organism, DomainError]:
        require_admin(auth)
        async with self._uow:
            if input.ncbi_tax_id is not None:
                existing = await self._repo.find_by_tax_id(
                    input.ncbi_tax_id, workspace_id=SHARED_WORKSPACE_ID
                )
                if existing is not None:
                    return Failure(
                        ConflictError(f"Organism with tax_id {input.ncbi_tax_id} already exists")
                    )
            # Organisms are reference data (design doc §1.5): every create writes
            # SHARED regardless of caller, so no tenant can ever own — and thus
            # mutate — one through the API.
            org = Organism.create(
                workspace_id=SHARED_WORKSPACE_ID,
                ncbi_tax_id=input.ncbi_tax_id,
                rank=input.rank,
                scientific_name=input.scientific_name,
                source=input.source,
                division=input.division,
                source_version=input.source_version,
            )
            await self._repo.save(org)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(org)
