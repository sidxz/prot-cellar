"""Unit tests for the pure enrichment mapper (GFF + essentiality -> records)."""

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


def test_emits_location_context_and_vulnerability_annotations() -> None:
    gff = [_gff("Rv0667", functional_category="Information pathways", gene_name="rpoB")]
    essentiality = {"Rv0667": "essential"}

    records = build_enrichment_records(gff, essentiality)
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

    vul = by_key["essentiality"]
    assert vul.axis is GeneAnnotationAxis.VULNERABILITY
    assert vul.value == "essential"
    assert vul.dataset == "DeJesus 2017"
    assert vul.condition == "in vitro 7H9"
    assert vul.evidence == "PMID:28096490"


def test_omits_context_annotation_when_no_functional_category() -> None:
    records = build_enrichment_records([_gff("Rv0667")], {"Rv0667": "essential"})
    keys = {a.key for a in records[0].annotations}
    assert "functional_category" not in keys
    assert "essentiality" in keys


def test_omits_vulnerability_annotation_when_locus_absent_from_essentiality() -> None:
    records = build_enrichment_records(
        [_gff("Rv0667", functional_category="Information pathways")], essentiality={}
    )
    keys = {a.key for a in records[0].annotations}
    assert "essentiality" not in keys
    assert "functional_category" in keys


def test_location_only_record_when_no_annotations_apply() -> None:
    records = build_enrichment_records([_gff("Rv0667")], {})
    rec = records[0]
    assert rec.genomic_accession == "NC_000962.3"
    assert rec.annotations == ()


def test_assembly_override_is_applied() -> None:
    records = build_enrichment_records([_gff("Rv0667")], {}, assembly="CustomASM")
    assert records[0].assembly == "CustomASM"


def test_essentiality_lookup_is_case_insensitive_on_locus() -> None:
    # GFF locus 'Rv0667' should match an essentiality key cased differently.
    records = build_enrichment_records([_gff("Rv0667")], {"rv0667": "growth-defect"})
    vul = next(a for a in records[0].annotations if a.key == "essentiality")
    assert vul.value == "growth-defect"
