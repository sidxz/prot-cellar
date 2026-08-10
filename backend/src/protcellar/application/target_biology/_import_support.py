"""Shared support for target-biology bulk-import commands.

``ItemResult`` is the per-row outcome (mirrors the protein_catalog bulk commands).
``build_locus_index`` resolves a gene from an external locus/name key exactly the
way ``BulkEnrichGenes`` does (primary_name / synonyms / source_record_id suffix,
upper-cased) — reused by every gene-side importer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

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


@dataclass(frozen=True, kw_only=True)
class LocusIndex:
    """``build_locus_index``'s result.

    ``.get(key)`` behaves exactly like the plain ``dict[str, Gene]`` it used to
    return — every one of the five existing bulk-upsert callers needs no change —
    except that a key two genes both claim now resolves to ``None`` (an honest
    miss) instead of silently keeping whichever gene was indexed first. ``ambiguous``
    is that missing detail for a caller that wants to say more than "unmatched":
    every gene that claimed a contested key, keyed the same upper-cased way.
    """

    _by_key: dict[str, Gene] = field(default_factory=dict)
    ambiguous: dict[str, list[Gene]] = field(default_factory=dict)

    def get(self, key: str) -> Gene | None:
        return self._by_key.get(key)


def build_locus_index(genes: Sequence[Gene]) -> LocusIndex:
    """Index genes by primary_name / synonyms / source_record_id suffix (upper-cased).

    A key claimed by two *different* genes is ambiguous: it is left out of the
    index entirely (so ``.get()`` reports a plain miss, same as an unmatched
    locus) and recorded in ``.ambiguous`` for a caller that wants to fail the
    row naming the candidates rather than accept a silent first-match.

    Protein-side importers resolve per-accession via ``find_by_accession`` instead —
    proteins are too numerous (100k+) to index in memory.
    """
    claims: dict[str, dict[object, Gene]] = {}
    for gene in genes:
        keys = [gene.primary_name, *gene.synonyms]
        if gene.source_record_id:
            keys.append(gene.source_record_id.split(":")[-1])
        for key in keys:
            if key:
                # Keyed by gene.id, not appended: a gene naming the same key twice
                # (e.g. its own primary_name repeated as a synonym) is one claim,
                # not a collision with itself.
                claims.setdefault(key.upper(), {})[gene.id] = gene

    by_key: dict[str, Gene] = {}
    ambiguous: dict[str, list[Gene]] = {}
    for key, by_gene_id in claims.items():
        if len(by_gene_id) > 1:
            ambiguous[key] = list(by_gene_id.values())
        else:
            (by_key[key],) = by_gene_id.values()
    return LocusIndex(_by_key=by_key, ambiguous=ambiguous)
