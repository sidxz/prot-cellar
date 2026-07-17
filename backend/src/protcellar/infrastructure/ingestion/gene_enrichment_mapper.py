"""Combine parsed GFF into ``GeneEnrichmentRecord``s.

Pure mapper (no I/O): for each :class:`GffGeneRecord` it emits one
:class:`GeneEnrichmentRecord` carrying the genomic location and a CONTEXT
``functional_category`` annotation (when the GFF has one). Essentiality is no
longer enriched here — it is ingested as target-biology ``Essentiality`` records
via the DeJesus plugin. All organism/source specifics live here, mirroring
``uniprot_mapper.py``.
"""

from __future__ import annotations

from collections.abc import Sequence

from protcellar.application.protein_catalog.bulk_enrich_genes import GeneEnrichmentRecord
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.infrastructure.ingestion.mycobrowser_gff import GffGeneRecord

_DEFAULT_ASSEMBLY = "ASM19595v2"
_MYCOBROWSER = "Mycobrowser"


def build_enrichment_records(
    gff: Sequence[GffGeneRecord],
    *,
    assembly: str = _DEFAULT_ASSEMBLY,
) -> list[GeneEnrichmentRecord]:
    """Map GFF records into enrichment records (location + functional category)."""
    records: list[GeneEnrichmentRecord] = []
    for feature in gff:
        annotations: list[GeneAnnotation] = []
        if feature.functional_category:
            annotations.append(
                GeneAnnotation(
                    axis=GeneAnnotationAxis.CONTEXT,
                    key="functional_category",
                    value=feature.functional_category,
                    dataset=_MYCOBROWSER,
                )
            )
        records.append(
            GeneEnrichmentRecord(
                locus_key=feature.locus_tag,
                genomic_accession=feature.seqid,
                genomic_start=feature.start,
                genomic_end=feature.end,
                genomic_strand=feature.strand,
                assembly=assembly,
                annotations=tuple(annotations),
            )
        )
    return records
