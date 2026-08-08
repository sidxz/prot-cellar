"""Idempotent bulk upsert of Hypomorph records, resolving genes by locus key.

Upsert key is (gene_id, condition, method). ``growth_defect_severity`` without
``growth_defect`` is rejected by the aggregate and reported failed. The knockdown
strain link is not resolved from the file (strain-name resolution is deferred);
put a strain designation in a future column once that lands.
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
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.repository import HypomorphRepository


@dataclass(frozen=True, kw_only=True)
class HypomorphImportRecord:
    locus_key: str
    growth_defect: bool
    growth_defect_severity: str | None = None
    condition: str | None = None
    method: str | None = None
    pmid: str | None = None
    dataset: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertHypomorphCommand(Command):
    organism_id: uuid.UUID
    records: tuple[HypomorphImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    dry_run: bool = False


class BulkUpsertHypomorph:
    def __init__(
        self,
        uow: UnitOfWork,
        gene_repo: GeneRepository,
        hypomorph_repo: HypomorphRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._gene_repo = gene_repo
        self._hyp_repo = hypomorph_repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: BulkUpsertHypomorphCommand, auth: AuthContext | None = None
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
                    existing = await self._hyp_repo.find_by_gene(SHARED_WORKSPACE_ID, gene.id)
                    match = next(
                        (
                            h
                            for h in existing
                            if h.condition == rec.condition and h.method == rec.method
                        ),
                        None,
                    )
                    if match is not None:
                        match.update(
                            growth_defect=rec.growth_defect,
                            growth_defect_severity=rec.growth_defect_severity,
                            condition=rec.condition,
                            method=rec.method,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._hyp_repo.save(match)
                        results.append(ItemResult(index=i, status="updated", id=str(match.id)))
                    else:
                        record = Hypomorph.create(
                            workspace_id=SHARED_WORKSPACE_ID,
                            gene_id=gene.id,
                            growth_defect=rec.growth_defect,
                            growth_defect_severity=rec.growth_defect_severity,
                            condition=rec.condition,
                            method=rec.method,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._hyp_repo.save(record)
                        results.append(ItemResult(index=i, status="created", id=str(record.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
