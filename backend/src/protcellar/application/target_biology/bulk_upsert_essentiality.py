"""Idempotent bulk upsert of Essentiality records, resolving genes by locus key.

Upsert key is (gene_id, condition, method): re-uploading the same call for the
same gene under the same condition/method updates in place rather than
duplicating. Genes are matched by locus like ``BulkEnrichGenes``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.application.target_biology._import_support import ItemResult, build_locus_index
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.repository import EssentialityRepository

# Accepts DeJesus codes and normalized strings; unknown -> UNCERTAIN.
_CLASSIFICATION: dict[str, EssentialityClass] = {
    "essential": EssentialityClass.ESSENTIAL,
    "es": EssentialityClass.ESSENTIAL,
    "esd": EssentialityClass.ESSENTIAL,
    "growth-defect": EssentialityClass.GROWTH_DEFECT,
    "growth_defect": EssentialityClass.GROWTH_DEFECT,
    "gd": EssentialityClass.GROWTH_DEFECT,
    "non-essential": EssentialityClass.NON_ESSENTIAL,
    "non_essential": EssentialityClass.NON_ESSENTIAL,
    "ne": EssentialityClass.NON_ESSENTIAL,
    "growth-advantage": EssentialityClass.GROWTH_ADVANTAGE,
    "growth_advantage": EssentialityClass.GROWTH_ADVANTAGE,
    "ga": EssentialityClass.GROWTH_ADVANTAGE,
    "uncertain": EssentialityClass.UNCERTAIN,
}


def classify(raw: str) -> EssentialityClass:
    return _CLASSIFICATION.get(raw.strip().lower(), EssentialityClass.UNCERTAIN)


@dataclass(frozen=True, kw_only=True)
class EssentialityImportRecord:
    locus_key: str
    classification: str
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    pmid: str | None = None
    dataset: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertEssentialityCommand(Command):
    organism_id: uuid.UUID
    records: tuple[EssentialityImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    generation_method: str = GenerationMethod.IMPORTED.value
    source_run_id: uuid.UUID | None = None
    dry_run: bool = False


def _provenance(
    source_type: str, generation_method: str, rec: EssentialityImportRecord
) -> Provenance:
    citations: tuple[Citation, ...] = ()
    if rec.pmid or rec.dataset:
        citations = (Citation(pmid=rec.pmid, label=rec.dataset),)
    return Provenance(
        source_type=ProvenanceSourceType(source_type),
        generation_method=GenerationMethod(generation_method),
        citations=citations,
    )


def _extensions(
    rec: EssentialityImportRecord, source_run_id: uuid.UUID | None
) -> dict[str, object]:
    ext: dict[str, object] = {"raw_call": rec.classification}
    if source_run_id is not None:
        # ponytail: source_run_id in the extensions bag (no migration); promote to
        # an indexed column when the v1.1 undo-a-run feature needs to query by it.
        ext["source_run_id"] = str(source_run_id)
    return ext


class BulkUpsertEssentiality:
    def __init__(
        self,
        uow: UnitOfWork,
        gene_repo: GeneRepository,
        essentiality_repo: EssentialityRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._gene_repo = gene_repo
        self._ess_repo = essentiality_repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: BulkUpsertEssentialityCommand, auth: AuthContext | None = None
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
                    classification = classify(rec.classification)
                    provenance = _provenance(input.source_type, input.generation_method, rec)
                    existing = await self._ess_repo.find_by_gene(SHARED_WORKSPACE_ID, gene.id)
                    match = next(
                        (
                            e
                            for e in existing
                            if e.condition == rec.condition and e.method == rec.method
                        ),
                        None,
                    )
                    if match is not None:
                        match.update(
                            classification=classification,
                            condition=rec.condition,
                            method=rec.method,
                            confidence=rec.confidence,
                            provenance=provenance,
                            extensions=_extensions(rec, input.source_run_id),
                        )
                        if not input.dry_run:
                            await self._ess_repo.save(match)
                        results.append(ItemResult(index=i, status="updated", id=str(match.id)))
                    else:
                        record = Essentiality.create(
                            workspace_id=SHARED_WORKSPACE_ID,
                            gene_id=gene.id,
                            classification=classification,
                            condition=rec.condition,
                            method=rec.method,
                            confidence=rec.confidence,
                            provenance=provenance,
                            extensions=_extensions(rec, input.source_run_id),
                        )
                        if not input.dry_run:
                            await self._ess_repo.save(record)
                        results.append(ItemResult(index=i, status="created", id=str(record.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
