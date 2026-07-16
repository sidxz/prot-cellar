"""UpdateOrganism command — partial update of an existing organism reference node."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.sentinel import UNSET
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class UpdateOrganismCommand(Command):
    organism_id: uuid.UUID
    scientific_name: str | None = None
    rank: str | None = None
    parent_id: uuid.UUID | None | object = UNSET
    division: str | None | object = UNSET
    reference_strain_id: uuid.UUID | None | object = UNSET
    source_version: str | None | object = UNSET


class UpdateOrganism:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: OrganismRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: UpdateOrganismCommand, auth: AuthContext | None = None
    ) -> Result[Organism, DomainError]:
        require_admin(auth)

        async with self._uow:
            org = await self._repo.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, input.organism_id)
            if org is None:
                return Failure(NotFoundError("Organism", str(input.organism_id)))

            # Build kwargs dict — only include fields that were provided
            fields: dict[str, Any] = {}
            if input.scientific_name is not None:
                fields["scientific_name"] = input.scientific_name
            if input.rank is not None:
                fields["rank"] = input.rank
            if input.parent_id is not UNSET:
                fields["parent_id"] = input.parent_id
            if input.division is not UNSET:
                fields["division"] = input.division
            if input.reference_strain_id is not UNSET:
                fields["reference_strain_id"] = input.reference_strain_id
            if input.source_version is not UNSET:
                fields["source_version"] = input.source_version

            if fields:
                org.update(**fields)
            await self._repo.save(org)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(org)
