"""CreateTarget command — register a new target in a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_editor, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.repository import TargetRepository
from protcellar.domain.target.target import Target, TargetComponent


@dataclass(frozen=True, kw_only=True)
class ComponentInput:
    protein_id: uuid.UUID
    relationship: ComponentRelationship


@dataclass(frozen=True, kw_only=True)
class CreateTargetCommand(Command):
    workspace_id: uuid.UUID
    pref_name: str
    target_type: TargetType
    components: tuple[ComponentInput, ...] = ()
    organism_id: uuid.UUID | None = None
    chembl_id: str | None = None
    pharmacological_class: str | None = None
    cross_references: tuple[CrossReference, ...] = field(default_factory=tuple)


class CreateTarget:
    def __init__(
        self, uow: UnitOfWork, repo: TargetRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateTargetCommand, auth: AuthContext | None = None
    ) -> Result[Target, DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            target = Target.create(
                workspace_id=input.workspace_id,
                pref_name=input.pref_name,
                target_type=input.target_type,
                components=[
                    TargetComponent(protein_id=c.protein_id, relationship=c.relationship)
                    for c in input.components
                ],
                organism_id=input.organism_id,
                chembl_id=input.chembl_id,
                pharmacological_class=input.pharmacological_class,
                cross_references=list(input.cross_references),
            )
            await self._repo.save(target)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(target)
