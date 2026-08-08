"""Idempotent bulk upsert of ResistanceMutation records, resolving genes by locus.

Upsert key is (gene_id, mutation, compound_id): the same variant can confer
resistance to several compounds (distinct rows). ``compound_id`` is a portable
chem-cellar molecule id supplied in the file; unresolved names stay unlinked.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.application.target_biology._import_support import (
    ItemResult,
    build_locus_index,
    provenance_from,
)
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import ProvenanceSourceType
from protcellar.domain.target_biology.repository import ResistanceMutationRepository
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation


@dataclass(frozen=True, kw_only=True)
class ResistanceMutationImportRecord:
    locus_key: str
    mutation: str
    compound_id: uuid.UUID | None = None
    compound_name: str | None = None
    mic_shift: float | None = None
    parent_strain: str | None = None
    protein_coordinate: str | None = None
    method: str | None = None
    pmid: str | None = None
    dataset: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertResistanceMutationCommand(Command):
    organism_id: uuid.UUID
    records: tuple[ResistanceMutationImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    dry_run: bool = False


def _compound(rec: ResistanceMutationImportRecord) -> CompoundRef | None:
    if rec.compound_id is None:
        return None
    return CompoundRef(compound_id=rec.compound_id, name=rec.compound_name)


def _compound_id(compound: CompoundRef | None) -> uuid.UUID | None:
    return compound.compound_id if compound is not None else None


class BulkUpsertResistanceMutation:
    def __init__(
        self,
        uow: UnitOfWork,
        gene_repo: GeneRepository,
        resistance_repo: ResistanceMutationRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._gene_repo = gene_repo
        self._rm_repo = resistance_repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: BulkUpsertResistanceMutationCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            index = build_locus_index(await self._gene_repo.list_by_organism(input.organism_id))
            for i, rec in enumerate(input.records):
                try:
                    gene = index.get(rec.locus_key.upper())
                    if gene is None:
                        results.append(
                            ItemResult(
                                index=i, status="failed", error=f"unmatched locus {rec.locus_key}"
                            )
                        )
                        continue
                    provenance = provenance_from(input.source_type, rec.pmid, rec.dataset)
                    compound = _compound(rec)
                    existing = await self._rm_repo.find_by_gene(SHARED_WORKSPACE_ID, gene.id)
                    match = next(
                        (
                            r
                            for r in existing
                            if r.mutation == rec.mutation.strip()
                            and _compound_id(r.compound) == rec.compound_id
                        ),
                        None,
                    )
                    if match is not None:
                        match.update(
                            compound=compound,
                            mic_shift=rec.mic_shift,
                            parent_strain=rec.parent_strain,
                            protein_coordinate=rec.protein_coordinate,
                            method=rec.method,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._rm_repo.save(match)
                        results.append(ItemResult(index=i, status="updated", id=str(match.id)))
                    else:
                        record = ResistanceMutation.create(
                            workspace_id=SHARED_WORKSPACE_ID,
                            gene_id=gene.id,
                            mutation=rec.mutation,
                            compound=compound,
                            mic_shift=rec.mic_shift,
                            parent_strain=rec.parent_strain,
                            protein_coordinate=rec.protein_coordinate,
                            method=rec.method,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._rm_repo.save(record)
                        results.append(ItemResult(index=i, status="created", id=str(record.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
