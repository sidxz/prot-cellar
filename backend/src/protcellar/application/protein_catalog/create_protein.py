"""Create a protein reference record (admin/service only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import ConflictError, DomainError


@dataclass(frozen=True, kw_only=True)
class CreateProteinCommand(Command):
    primary_accession: str
    organism_id: uuid.UUID
    sequence: str
    is_reviewed: bool = False
    secondary_accessions: list[str] = field(default_factory=list)
    entry_name: str | None = None
    protein_names: ProteinNames | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: list[str] = field(default_factory=list)
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: list[CrossReference] = field(default_factory=list)


class CreateProtein:
    def __init__(
        self, uow: UnitOfWork, repo: ProteinRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateProteinCommand, auth: AuthContext | None = None
    ) -> Result[Protein, DomainError]:
        require_admin(auth)
        async with self._uow:
            existing = await self._repo.find_by_accession(input.primary_accession)
            if existing is not None:
                return Failure(
                    ConflictError(f"Protein '{input.primary_accession}' already exists")
                )
            protein = Protein.create(
                primary_accession=input.primary_accession,
                organism_id=input.organism_id,
                sequence=input.sequence,
                is_reviewed=input.is_reviewed,
                secondary_accessions=list(input.secondary_accessions),
                entry_name=input.entry_name,
                protein_names=input.protein_names,
                strain_id=input.strain_id,
                gene_id=input.gene_id,
                seq_mass=input.seq_mass,
                seq_crc64=input.seq_crc64,
                protein_existence=input.protein_existence,
                keywords=list(input.keywords),
                entry_version=input.entry_version,
                sequence_version=input.sequence_version,
                cross_references=list(input.cross_references),
            )
            await self._repo.save(protein)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(protein)
