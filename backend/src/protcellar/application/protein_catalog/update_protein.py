"""UpdateProtein command — partial update of an existing protein reference record."""

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
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError, NotFoundError


@dataclass(frozen=True, kw_only=True)
class UpdateProteinCommand(Command):
    accession: str
    sequence: str | None = None
    is_reviewed: bool | None = None
    secondary_accessions: list[str] | None = None
    entry_name: str | None | object = UNSET
    protein_names: ProteinNames | None | object = UNSET
    strain_id: uuid.UUID | None | object = UNSET
    gene_id: uuid.UUID | None | object = UNSET
    seq_mass: int | None | object = UNSET
    seq_crc64: str | None | object = UNSET
    protein_existence: ProteinExistence | None | object = UNSET
    keywords: list[str] | None = None
    entry_version: int | None | object = UNSET
    sequence_version: int | None | object = UNSET
    cross_references: list[CrossReference] | None = None


class UpdateProtein:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: ProteinRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: UpdateProteinCommand, auth: AuthContext | None = None
    ) -> Result[Protein, DomainError]:
        require_admin(auth)

        async with self._uow:
            protein = await self._repo.find_owned_by_accession(
                input.accession,
                workspace_id=auth.workspace_id,  # type: ignore[union-attr]
            )
            if protein is None:
                return Failure(NotFoundError("Protein", input.accession))

            # Build kwargs dict — only include fields that were provided
            fields: dict[str, Any] = {}
            if input.sequence is not None:
                fields["sequence"] = input.sequence
            if input.is_reviewed is not None:
                fields["is_reviewed"] = input.is_reviewed
            if input.secondary_accessions is not None:
                fields["secondary_accessions"] = input.secondary_accessions
            if input.entry_name is not UNSET:
                fields["entry_name"] = input.entry_name
            if input.protein_names is not UNSET:
                fields["protein_names"] = input.protein_names
            if input.strain_id is not UNSET:
                fields["strain_id"] = input.strain_id
            if input.gene_id is not UNSET:
                fields["gene_id"] = input.gene_id
            if input.seq_mass is not UNSET:
                fields["seq_mass"] = input.seq_mass
            if input.seq_crc64 is not UNSET:
                fields["seq_crc64"] = input.seq_crc64
            if input.protein_existence is not UNSET:
                fields["protein_existence"] = input.protein_existence
            if input.keywords is not None:
                fields["keywords"] = input.keywords
            if input.entry_version is not UNSET:
                fields["entry_version"] = input.entry_version
            if input.sequence_version is not UNSET:
                fields["sequence_version"] = input.sequence_version
            if input.cross_references is not None:
                fields["cross_references"] = input.cross_references

            if fields:
                protein.update(**fields)
            await self._repo.save(protein)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(protein)
