"""Idempotent bulk upsert of gene reference records, keyed on (source, source_record_id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.protein_catalog.bulk_upsert_proteins import ItemResult
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class GeneImportRecord:
    primary_name: str
    organism_id: uuid.UUID
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    strain_id: uuid.UUID | None = None
    synonyms: tuple[str, ...] = ()
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    cross_references: tuple[CrossReference, ...] = ()


@dataclass(frozen=True, kw_only=True)
class BulkUpsertGenesCommand(Command):
    records: tuple[GeneImportRecord, ...]
    dry_run: bool = False


class BulkUpsertGenes:
    def __init__(
        self, uow: UnitOfWork, repo: GeneRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: BulkUpsertGenesCommand, auth: AuthContext | None = None
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
                        # A record without a strain (e.g. the /genes/bulk route,
                        # which doesn't expose strain_id) must NOT wipe a strain the
                        # proteome import already resolved — only set when provided.
                        update_fields: dict[str, Any] = {
                            "primary_name": rec.primary_name,
                            "synonyms": list(rec.synonyms),
                            "ncbi_gene_id": rec.ncbi_gene_id,
                            "ensembl_gene_id": rec.ensembl_gene_id,
                            "cross_references": list(rec.cross_references),
                        }
                        if rec.strain_id is not None:
                            update_fields["strain_id"] = rec.strain_id
                        existing.update(**update_fields)
                        existing.source_record_checksum = rec.source_record_checksum
                        existing.source_release = rec.source_release
                        existing.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(existing)
                        results.append(ItemResult(index=i, status="updated", id=str(existing.id)))
                    else:
                        gene = Gene.create(
                            primary_name=rec.primary_name,
                            organism_id=rec.organism_id,
                            strain_id=rec.strain_id,
                            synonyms=list(rec.synonyms),
                            ncbi_gene_id=rec.ncbi_gene_id,
                            ensembl_gene_id=rec.ensembl_gene_id,
                            cross_references=list(rec.cross_references),
                        )
                        gene.source = rec.source
                        gene.source_record_id = rec.source_record_id
                        gene.source_record_checksum = rec.source_record_checksum
                        gene.source_release = rec.source_release
                        gene.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(gene)
                        results.append(ItemResult(index=i, status="created", id=str(gene.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
