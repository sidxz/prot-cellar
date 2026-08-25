"""CreateTarget command — register a new target in a workspace."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_editor, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.application.target.default_pref_name import component_label, default_pref_name
from protcellar.domain.protein_catalog.repository import GeneRepository, ProteinRepository
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
    target_type: TargetType
    pref_name: str | None = None
    """Omitted -> derived from the component proteins (see default_pref_name)."""
    components: tuple[ComponentInput, ...] = ()
    organism_id: uuid.UUID | None = None
    chembl_id: str | None = None
    pharmacological_class: str | None = None
    cross_references: tuple[CrossReference, ...] = field(default_factory=tuple)


class CreateTarget:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: TargetRepository,
        proteins: ProteinRepository,
        genes: GeneRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher
        self._proteins, self._genes = proteins, genes

    async def _derive_pref_name(self, input: CreateTargetCommand) -> str:
        labels: list[str] = []
        for c in input.components:
            protein = await self._proteins.find_readable(input.workspace_id, c.protein_id)
            if protein is None:
                continue
            gene = (
                await self._genes.find_readable(input.workspace_id, protein.gene_id)
                if protein.gene_id
                else None
            )
            labels.append(component_label(protein, gene))
        return default_pref_name(input.target_type, labels)

    async def __call__(
        self, input: CreateTargetCommand, auth: AuthContext | None = None
    ) -> Result[Target, DomainError]:
        require_editor(auth)
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            pref_name = input.pref_name or await self._derive_pref_name(input)
            target = Target.create(
                workspace_id=input.workspace_id,
                pref_name=pref_name,
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
