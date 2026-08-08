"""CreateStrain command — register a new strain in a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_editor, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.repository import StrainRepository
from protcellar.domain.taxonomy.strain import Strain


@dataclass(frozen=True, kw_only=True)
class CreateStrainCommand(Command):
    workspace_id: uuid.UUID
    species_organism_id: uuid.UUID
    name: str
    ncbi_taxon_id: int | None = None
    isolate: str | None = None
    biosample_acc: str | None = None
    assembly_acc: str | None = None
    culture_collection: str | None = None
    host_organism_id: uuid.UUID | None = None
    metadata: dict[str, object] | None = None


class CreateStrain:
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
        self, input: CreateStrainCommand, auth: AuthContext | None = None
    ) -> Result[Strain, DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)

        async with self._uow:
            # Strains are reference data too (design doc §1.5, same section as
            # organisms/proteomes): every create writes SHARED regardless of the
            # caller's own workspace. input.workspace_id is still validated above
            # (the caller must be who they say they are) — it just no longer
            # decides where the row lands.
            strain = Strain.create(
                workspace_id=SHARED_WORKSPACE_ID,
                species_organism_id=input.species_organism_id,
                name=input.name,
                ncbi_taxon_id=input.ncbi_taxon_id,
                isolate=input.isolate,
                biosample_acc=input.biosample_acc,
                assembly_acc=input.assembly_acc,
                culture_collection=input.culture_collection,
                host_organism_id=input.host_organism_id,
                metadata=input.metadata,
            )
            await self._repo.save(strain)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(strain)
