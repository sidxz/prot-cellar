"""Idempotent enrichment of existing genes, matched by locus tag within an organism.

Each :class:`GeneEnrichmentRecord` carries optional genomic-location fields and a
batch of dataset-scoped :class:`GeneAnnotation`s. The use case loads every gene
for the organism, indexes them by locus tag (``primary_name`` / every synonym /
``source_record_id`` suffix, all upper-cased), then for each record **sets** the
location fields present and **merges** annotations by ``(dataset, key)`` — so a
re-import replaces colliding annotations in place rather than appending duplicates.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError

_LOCATION_FIELDS = (
    "genomic_accession",
    "genomic_start",
    "genomic_end",
    "genomic_strand",
    "assembly",
)


@dataclass(frozen=True, kw_only=True)
class GeneEnrichmentRecord:
    """A locus-keyed bundle of location + annotation facts to merge onto a gene."""

    locus_key: str
    genomic_accession: str | None = None
    genomic_start: int | None = None
    genomic_end: int | None = None
    genomic_strand: str | None = None
    assembly: str | None = None
    annotations: tuple[GeneAnnotation, ...] = ()


@dataclass(frozen=True, kw_only=True)
class EnrichSummary:
    """Tally of one enrichment pass."""

    matched: int = 0
    unmatched: int = 0
    locations_set: int = 0
    annotations_written: int = 0
    unmatched_loci: list[str] = field(default_factory=list)


class BulkEnrichGenes:
    def __init__(
        self, uow: UnitOfWork, gene_repo: GeneRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, gene_repo, dispatcher

    async def __call__(
        self,
        organism_id: uuid.UUID,
        records: Sequence[GeneEnrichmentRecord],
        auth: AuthContext | None = None,
    ) -> Result[EnrichSummary, DomainError]:
        require_admin(auth)
        matched = locations_set = annotations_written = 0
        unmatched_loci: list[str] = []
        async with self._uow:
            index = self._build_index(await self._repo.list_by_organism(organism_id))
            for rec in records:
                gene = index.get(rec.locus_key.upper())
                if gene is None:
                    unmatched_loci.append(rec.locus_key)
                    continue
                matched += 1
                location = self._location_fields(rec)
                merged = self._merge_annotations(gene.annotations, rec.annotations)
                if location:
                    locations_set += 1
                if rec.annotations:
                    annotations_written += len(rec.annotations)
                if location or rec.annotations:
                    gene.update(**location, annotations=merged)
                    await self._repo.save(gene)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(
            EnrichSummary(
                matched=matched,
                unmatched=len(unmatched_loci),
                locations_set=locations_set,
                annotations_written=annotations_written,
                unmatched_loci=unmatched_loci,
            )
        )

    @staticmethod
    def _build_index(genes: Sequence[Gene]) -> dict[str, Gene]:
        index: dict[str, Gene] = {}
        for gene in genes:
            keys = [gene.primary_name, *gene.synonyms]
            if gene.source_record_id:
                keys.append(gene.source_record_id.split(":")[-1])
            for key in keys:
                if key:
                    index.setdefault(key.upper(), gene)
        return index

    @staticmethod
    def _location_fields(rec: GeneEnrichmentRecord) -> dict[str, object]:
        return {f: getattr(rec, f) for f in _LOCATION_FIELDS if getattr(rec, f) is not None}

    @staticmethod
    def _merge_annotations(
        existing: Sequence[GeneAnnotation], incoming: Sequence[GeneAnnotation]
    ) -> list[GeneAnnotation]:
        """Drop existing annotations colliding on ``(dataset, key)``, then append incoming."""
        collisions = {(a.dataset, a.key) for a in incoming}
        kept = [a for a in existing if (a.dataset, a.key) not in collisions]
        return [*kept, *incoming]
