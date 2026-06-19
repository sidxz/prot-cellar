"""UpdateTarget command — partial update of an existing target."""

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
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.target.enums import TargetType
from protcellar.domain.target.repository import TargetRepository
from protcellar.domain.target.target import Target, TargetComponent

from .create_target import ComponentInput


@dataclass(frozen=True, kw_only=True)
class UpdateTargetCommand(Command):
    workspace_id: uuid.UUID
    target_id: uuid.UUID
    pref_name: str | None = None
    target_type: TargetType | None = None
    components: tuple[ComponentInput, ...] | None = None
    organism_id: uuid.UUID | None | object = UNSET
    chembl_id: str | None | object = UNSET
    pharmacological_class: str | None | object = UNSET
    cross_references: tuple[CrossReference, ...] | None = None


class UpdateTarget:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: TargetRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: UpdateTargetCommand, auth: AuthContext | None = None
    ) -> Result[Target, DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)

        async with self._uow:
            target = await self._repo.find_by_id_in_workspace(input.workspace_id, input.target_id)
            if target is None:
                return Failure(NotFoundError("Target", str(input.target_id)))

            fields: dict[str, Any] = {}
            if input.pref_name is not None:
                fields["pref_name"] = input.pref_name
            if input.target_type is not None:
                fields["target_type"] = input.target_type
            if input.components is not None:
                fields["components"] = [
                    TargetComponent(protein_id=c.protein_id, relationship=c.relationship)
                    for c in input.components
                ]
            if input.organism_id is not UNSET:
                fields["organism_id"] = input.organism_id
            if input.chembl_id is not UNSET:
                fields["chembl_id"] = input.chembl_id
            if input.pharmacological_class is not UNSET:
                fields["pharmacological_class"] = input.pharmacological_class
            if input.cross_references is not None:
                fields["cross_references"] = list(input.cross_references)

            if fields:
                target.update(**fields)
            await self._repo.save(target)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(target)
