"""Shared support for target-biology bulk-import commands.

``ItemResult`` is the per-row outcome (mirrors the protein_catalog bulk commands).
``build_locus_index`` resolves a gene from an external locus/name key exactly the
way ``BulkEnrichGenes`` does (primary_name / synonyms / source_record_id suffix,
upper-cased) — reused by every gene-side importer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType


@dataclass(frozen=True, kw_only=True)
class ItemResult:
    index: int
    status: str  # "created" | "updated" | "skipped" | "failed"
    id: str | None = None
    error: str | None = None


def provenance_from(source_type: str, pmid: str | None, dataset: str | None) -> Provenance:
    """Build the shared Provenance envelope from a source type + optional citation."""
    citations: tuple[Citation, ...] = ()
    if pmid or dataset:
        citations = (Citation(pmid=pmid, label=dataset),)
    return Provenance(source_type=ProvenanceSourceType(source_type), citations=citations)


def build_locus_index(genes: Sequence[Gene]) -> dict[str, Gene]:
    """Index genes by primary_name / synonyms / source_record_id suffix (upper-cased).

    Protein-side importers resolve per-accession via ``find_by_accession`` instead —
    proteins are too numerous (100k+) to index in memory.
    """
    index: dict[str, Gene] = {}
    for gene in genes:
        keys = [gene.primary_name, *gene.synonyms]
        if gene.source_record_id:
            keys.append(gene.source_record_id.split(":")[-1])
        for key in keys:
            if key:
                index.setdefault(key.upper(), gene)
    return index
