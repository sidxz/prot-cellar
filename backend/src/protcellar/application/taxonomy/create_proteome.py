"""Create a proteome reference record (admin/service only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import ConflictError, DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.domain.taxonomy.repository import ProteomeRepository


@dataclass(frozen=True, kw_only=True)
class CreateProteomeCommand(Command):
    uniprot_proteome_id: str
    organism_id: uuid.UUID
    proteome_type: ProteomeType
    is_reference: bool
    strain_id: uuid.UUID | None = None
    assembly_acc: str | None = None
    source_version: str | None = None


class CreateProteome:
    def __init__(
        self, uow: UnitOfWork, repo: ProteomeRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateProteomeCommand, auth: AuthContext | None = None
    ) -> Result[Proteome, DomainError]:
        require_admin(auth)
        async with self._uow:
            existing = await self._repo.find_by_proteome_id(input.uniprot_proteome_id)
            if existing is not None:
                return Failure(
                    ConflictError(f"Proteome with id {input.uniprot_proteome_id} already exists")
                )
            # Proteomes are reference data (design doc §1.5), same as organisms.
            proteome = Proteome.create(
                workspace_id=SHARED_WORKSPACE_ID,
                uniprot_proteome_id=input.uniprot_proteome_id,
                organism_id=input.organism_id,
                proteome_type=input.proteome_type,
                is_reference=input.is_reference,
                strain_id=input.strain_id,
                assembly_acc=input.assembly_acc,
                source_version=input.source_version,
            )
            await self._repo.save(proteome)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(proteome)
