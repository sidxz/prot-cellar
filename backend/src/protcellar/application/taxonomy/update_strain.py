"""UpdateStrain command — partial update of an existing strain."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_editor, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.sentinel import UNSET
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.taxonomy.repository import StrainRepository
from protcellar.domain.taxonomy.strain import Strain


@dataclass(frozen=True, kw_only=True)
class UpdateStrainCommand(Command):
    workspace_id: uuid.UUID
    strain_id: uuid.UUID
    name: str | None = None
    strain_organism_id: uuid.UUID | None | object = UNSET
    isolate: str | None | object = UNSET
    biosample_acc: str | None | object = UNSET
    assembly_acc: str | None | object = UNSET
    culture_collection: str | None | object = UNSET
    host_organism_id: uuid.UUID | None | object = UNSET
    metadata: dict | None | object = UNSET


class UpdateStrain:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: StrainRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: UpdateStrainCommand, auth: AuthContext | None = None
    ) -> Result[Strain, DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)

        async with self._uow:
            strain = await self._repo.find_by_id_in_workspace(input.workspace_id, input.strain_id)
            if strain is None:
                return Failure(NotFoundError("Strain", str(input.strain_id)))

            fields: dict[str, Any] = {}
            if input.name is not None:
                fields["name"] = input.name
            if input.strain_organism_id is not UNSET:
                fields["strain_organism_id"] = input.strain_organism_id
            if input.isolate is not UNSET:
                fields["isolate"] = input.isolate
            if input.biosample_acc is not UNSET:
                fields["biosample_acc"] = input.biosample_acc
            if input.assembly_acc is not UNSET:
                fields["assembly_acc"] = input.assembly_acc
            if input.culture_collection is not UNSET:
                fields["culture_collection"] = input.culture_collection
            if input.host_organism_id is not UNSET:
                fields["host_organism_id"] = input.host_organism_id
            if input.metadata is not UNSET:
                fields["metadata"] = input.metadata

            if fields:
                strain.update(**fields)
            await self._repo.save(strain)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(strain)
