"""Idempotent bulk upsert of CrispriStrain records, resolving the target gene by locus.

Upsert key is (target_gene_id, name): re-uploading the same strain name for the
same target gene updates in place.
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
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import ProvenanceSourceType
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.repository import CrispriStrainRepository


@dataclass(frozen=True, kw_only=True)
class CrispriStrainImportRecord:
    locus_key: str  # the target gene the strain knocks down
    name: str
    pmid: str | None = None
    dataset: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertCrispriStrainCommand(Command):
    organism_id: uuid.UUID
    records: tuple[CrispriStrainImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    dry_run: bool = False


class BulkUpsertCrispriStrain:
    def __init__(
        self,
        uow: UnitOfWork,
        gene_repo: GeneRepository,
        crispri_repo: CrispriStrainRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._gene_repo = gene_repo
        self._cs_repo = crispri_repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: BulkUpsertCrispriStrainCommand, auth: AuthContext | None = None
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
                    existing = await self._cs_repo.find_owned_by_gene(SHARED_WORKSPACE_ID, gene.id)
                    match = next((s for s in existing if s.name == rec.name.strip()), None)
                    if match is not None:
                        match.update(provenance=provenance)
                        if not input.dry_run:
                            await self._cs_repo.save(match)
                        results.append(ItemResult(index=i, status="updated", id=str(match.id)))
                    else:
                        record = CrispriStrain.create(
                            workspace_id=SHARED_WORKSPACE_ID,
                            name=rec.name,
                            target_gene_id=gene.id,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._cs_repo.save(record)
                        results.append(ItemResult(index=i, status="created", id=str(record.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
