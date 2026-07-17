"""Unit tests for the pure enrichment mapper (GFF -> records)."""

from __future__ import annotations

from protcellar.application.protein_catalog.bulk_enrich_genes import GeneEnrichmentRecord
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotationAxis
from protcellar.infrastructure.ingestion.gene_enrichment_mapper import build_enrichment_records
from protcellar.infrastructure.ingestion.mycobrowser_gff import GffGeneRecord


def _gff(
    locus: str,
    *,
    functional_category: str | None = None,
    gene_name: str | None = None,
    product: str | None = None,
) -> GffGeneRecord:
    return GffGeneRecord(
        locus_tag=locus,
        seqid="NC_000962.3",
        start=759807,
        end=763325,
        strand="+",
        gene_name=gene_name,
        product=product,
        functional_category=functional_category,
    )


def test_emits_location_and_context_annotation() -> None:
    gff = [_gff("Rv0667", functional_category="Information pathways", gene_name="rpoB")]
    records = build_enrichment_records(gff)
    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, GeneEnrichmentRecord)

    # Location set from the GFF record.
    assert rec.locus_key == "Rv0667"
    assert rec.genomic_accession == "NC_000962.3"
    assert rec.genomic_start == 759807
    assert rec.genomic_end == 763325
    assert rec.genomic_strand == "+"
    assert rec.assembly == "ASM19595v2"

    by_key = {a.key: a for a in rec.annotations}
    ctx = by_key["functional_category"]
    assert ctx.axis is GeneAnnotationAxis.CONTEXT
    assert ctx.value == "Information pathways"
    assert ctx.dataset == "Mycobrowser"


def test_omits_context_annotation_when_no_functional_category() -> None:
    records = build_enrichment_records([_gff("Rv0667")])
    assert records[0].annotations == ()


def test_never_emits_essentiality_annotation() -> None:
    # Essentiality is ingested as target-biology records via the plugin now; the
    # mapper must never emit a VULNERABILITY essentiality annotation.
    records = build_enrichment_records([_gff("Rv0667", functional_category="Info pathways")])
    keys = {a.key for a in records[0].annotations}
    assert "essentiality" not in keys
    assert not any(a.axis is GeneAnnotationAxis.VULNERABILITY for a in records[0].annotations)


def test_assembly_override_is_applied() -> None:
    records = build_enrichment_records([_gff("Rv0667")], assembly="CustomASM")
    assert records[0].assembly == "CustomASM"
