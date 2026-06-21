"""Combine parsed GFF + essentiality into ``GeneEnrichmentRecord``s.

Pure mapper (no I/O): for each :class:`GffGeneRecord` it emits one
:class:`GeneEnrichmentRecord` carrying the genomic location, a CONTEXT
``functional_category`` annotation (when the GFF has one) and a VULNERABILITY
``essentiality`` annotation (when the locus appears in the DeJesus call map).
All organism/source specifics live here, mirroring ``uniprot_mapper.py``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from protcellar.application.protein_catalog.bulk_enrich_genes import GeneEnrichmentRecord
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.infrastructure.ingestion.mycobrowser_gff import GffGeneRecord

_DEFAULT_ASSEMBLY = "ASM19595v2"
_MYCOBROWSER = "Mycobrowser"
_DEJESUS_DATASET = "DeJesus 2017"
_DEJESUS_CONDITION = "in vitro 7H9"
_DEJESUS_EVIDENCE = "PMID:28096490"


def build_enrichment_records(
    gff: Sequence[GffGeneRecord],
    essentiality: Mapping[str, str],
    *,
    assembly: str = _DEFAULT_ASSEMBLY,
) -> list[GeneEnrichmentRecord]:
    """Map GFF records (+ essentiality calls) into enrichment records."""
    calls = {locus.upper(): value for locus, value in essentiality.items()}
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
        call = calls.get(feature.locus_tag.upper())
        if call:
            annotations.append(
                GeneAnnotation(
                    axis=GeneAnnotationAxis.VULNERABILITY,
                    key="essentiality",
                    value=call,
                    dataset=_DEJESUS_DATASET,
                    condition=_DEJESUS_CONDITION,
                    evidence=_DEJESUS_EVIDENCE,
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
