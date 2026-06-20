"""Idempotent bulk upsert of protein reference records, keyed on (source, source_record_id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class ProteinImportRecord:
    primary_accession: str
    organism_id: uuid.UUID
    sequence: str
    is_reviewed: bool
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    secondary_accessions: tuple[str, ...] = ()
    entry_name: str | None = None
    protein_names: ProteinNames | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: tuple[str, ...] = ()
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: tuple[CrossReference, ...] = ()
    annotation_score: int | None = None
    fragment: str | None = None
    uniparc_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertProteinsCommand(Command):
    records: tuple[ProteinImportRecord, ...]
    dry_run: bool = False


@dataclass(frozen=True, kw_only=True)
class ItemResult:
    index: int
    status: str  # created | updated | skipped | failed
    id: str | None = None
    error: str | None = None


class BulkUpsertProteins:
    def __init__(
        self, uow: UnitOfWork, repo: ProteinRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: BulkUpsertProteinsCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            for i, rec in enumerate(input.records):
                try:
                    existing = await self._repo.find_by_source_record_id(
                        rec.source, rec.source_record_id
                    )
                    if existing is not None:
                        if existing.source_record_checksum == rec.source_record_checksum:
                            results.append(
                                ItemResult(index=i, status="skipped", id=str(existing.id))
                            )
                            continue
                        existing.update(
                            sequence=rec.sequence,
                            is_reviewed=rec.is_reviewed,
                            entry_name=rec.entry_name,
                            protein_names=rec.protein_names,
                            secondary_accessions=list(rec.secondary_accessions),
                            strain_id=rec.strain_id,
                            gene_id=rec.gene_id,
                            seq_mass=rec.seq_mass,
                            seq_crc64=rec.seq_crc64,
                            protein_existence=rec.protein_existence,
                            keywords=list(rec.keywords),
                            entry_version=rec.entry_version,
                            sequence_version=rec.sequence_version,
                            cross_references=list(rec.cross_references),
                            annotation_score=rec.annotation_score,
                            fragment=rec.fragment,
                            uniparc_id=rec.uniparc_id,
                        )
                        existing.source_record_checksum = rec.source_record_checksum
                        existing.source_release = rec.source_release
                        existing.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(existing)
                        results.append(ItemResult(index=i, status="updated", id=str(existing.id)))
                    else:
                        protein = Protein.create(
                            primary_accession=rec.primary_accession,
                            organism_id=rec.organism_id,
                            sequence=rec.sequence,
                            is_reviewed=rec.is_reviewed,
                            secondary_accessions=list(rec.secondary_accessions),
                            entry_name=rec.entry_name,
                            protein_names=rec.protein_names,
                            strain_id=rec.strain_id,
                            gene_id=rec.gene_id,
                            seq_mass=rec.seq_mass,
                            seq_crc64=rec.seq_crc64,
                            protein_existence=rec.protein_existence,
                            keywords=list(rec.keywords),
                            entry_version=rec.entry_version,
                            sequence_version=rec.sequence_version,
                            cross_references=list(rec.cross_references),
                            annotation_score=rec.annotation_score,
                            fragment=rec.fragment,
                            uniparc_id=rec.uniparc_id,
                        )
                        protein.source = rec.source
                        protein.source_record_id = rec.source_record_id
                        protein.source_record_checksum = rec.source_record_checksum
                        protein.source_release = rec.source_release
                        protein.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(protein)
                        results.append(ItemResult(index=i, status="created", id=str(protein.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                # no commit on dry run
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
