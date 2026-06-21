"""Unit tests for the pure Mycobrowser GFF3 parser (no network / DB)."""

from __future__ import annotations

from protcellar.infrastructure.ingestion.mycobrowser_gff import (
    GffGeneRecord,
    parse_mycobrowser_gff,
)

# Mycobrowser-style H37Rv GFF3: a `gene` line carrying coords + a sibling `CDS`
# carrying Functional_Category/Product, both keyed by the same locus tag. Uses
# Mycobrowser's native attribute vocabulary (Locus/Name/Functional_Category/Product).
_FIXTURE = """##gff-version 3
#!genome-build ASM19595v2
NC_000962.3	Mycobrowser	gene	759807	763325	.	+	.	Locus=Rv0667;Name=rpoB
NC_000962.3	Mycobrowser	CDS	759807	763325	.	+	0	Locus=Rv0667;Name=rpoB;Functional_Category=Information pathways;Product=DNA-directed RNA polymerase subunit beta RpoB
NC_000962.3	Mycobrowser	gene	2153889	2156111	.	-	.	Locus=Rv1908c;Name=katG;Functional_Category=Virulence%2C detoxification%2C adaptation;Product=Catalase-peroxidase KatG
"""

# Standard NCBI/RefSeq attribute vocabulary (locus_tag/gene/product) on a single
# feature — the parser must understand both vocabularies.
_FIXTURE_NCBI = """##gff-version 3
NC_000962.3	RefSeq	gene	1	1524	.	+	.	ID=gene-Rv0001;locus_tag=Rv0001;gene=dnaA
NC_000962.3	RefSeq	CDS	1	1524	.	+	0	locus_tag=Rv0001;gene=dnaA;product=Chromosomal replication initiator protein DnaA
"""


def test_parses_locus_coords_strand_name_and_functional_category() -> None:
    records = parse_mycobrowser_gff(_FIXTURE)
    by_locus = {r.locus_tag: r for r in records}
    assert set(by_locus) == {"Rv0667", "Rv1908c"}

    rpob = by_locus["Rv0667"]
    assert rpob.seqid == "NC_000962.3"
    assert rpob.start == 759807
    assert rpob.end == 763325
    assert rpob.strand == "+"
    assert rpob.gene_name == "rpoB"
    assert rpob.functional_category == "Information pathways"
    assert rpob.product == "DNA-directed RNA polymerase subunit beta RpoB"


def test_coalesces_gene_and_cds_by_locus() -> None:
    # Functional_Category/Product live on the CDS line; coords on the gene line.
    # A single coalesced record must carry both.
    records = parse_mycobrowser_gff(_FIXTURE)
    rpob = next(r for r in records if r.locus_tag == "Rv0667")
    assert rpob.start == 759807  # from gene line
    assert rpob.functional_category == "Information pathways"  # from CDS line


def test_url_decodes_attribute_values() -> None:
    records = parse_mycobrowser_gff(_FIXTURE)
    katg = next(r for r in records if r.locus_tag == "Rv1908c")
    assert katg.strand == "-"
    assert katg.functional_category == "Virulence, detoxification, adaptation"


def test_understands_ncbi_attribute_vocabulary() -> None:
    records = parse_mycobrowser_gff(_FIXTURE_NCBI)
    rec = next(r for r in records if r.locus_tag == "Rv0001")
    assert rec.gene_name == "dnaA"
    assert rec.product == "Chromosomal replication initiator protein DnaA"
    assert rec.start == 1
    assert rec.end == 1524


def test_skips_features_without_a_locus_tag() -> None:
    text = (
        "##gff-version 3\n"
        "NC_000962.3\tRefSeq\tregion\t1\t4411532\t.\t+\t.\tID=NC_000962.3;Dbxref=taxon:83332\n"
        "NC_000962.3\tMycobrowser\tgene\t1\t100\t.\t+\t.\tLocus=Rv0000;Name=foo\n"
    )
    records = parse_mycobrowser_gff(text)
    assert [r.locus_tag for r in records] == ["Rv0000"]


def test_returns_gff_gene_record_instances() -> None:
    records = parse_mycobrowser_gff(_FIXTURE)
    assert all(isinstance(r, GffGeneRecord) for r in records)
