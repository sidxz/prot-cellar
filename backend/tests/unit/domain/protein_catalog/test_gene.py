import uuid

import pytest

from protcellar.domain.protein_catalog.events import GeneCreated, GeneUpdated
from protcellar.domain.protein_catalog.gene import Gene, gene_display_label
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID


def test_create_gene() -> None:
    organism = uuid.uuid4()
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="TP53",
        organism_id=organism,
        synonyms=["P53", "LFS1"],
    )
    assert gene.primary_name == "TP53"
    assert gene.organism_id == organism
    assert gene.synonyms == ["P53", "LFS1"]
    assert gene.workspace_id == SHARED_WORKSPACE_ID
    assert gene.version == 1
    events = gene.collect_events()
    assert len(events) == 1 and isinstance(events[0], GeneCreated)


def test_create_requires_primary_name() -> None:
    with pytest.raises(ValidationError):
        Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="   ", organism_id=uuid.uuid4())


def test_update_gene_fields() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="TP53", organism_id=uuid.uuid4()
    )
    gene.update(ncbi_gene_id="7157", ensembl_gene_id="ENSG00000141510")
    assert gene.ncbi_gene_id == "7157"
    assert gene.ensembl_gene_id == "ENSG00000141510"
    assert any(isinstance(e, GeneUpdated) for e in gene.collect_events())


def test_gene_carries_strain() -> None:
    # A gene belongs to a specific strain's genome (null for single-genome species).
    strain = uuid.uuid4()
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="rpoB",
        organism_id=uuid.uuid4(),
        strain_id=strain,
    )
    assert gene.strain_id == strain
    other = uuid.uuid4()
    gene.update(strain_id=other)
    assert gene.strain_id == other
    human = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="TP53", organism_id=uuid.uuid4()
    )
    assert human.strain_id is None


def test_update_rejects_empty_primary_name() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="TP53", organism_id=uuid.uuid4()
    )
    with pytest.raises(ValidationError):
        gene.update(primary_name="  ")


def test_gene_holds_genomic_location_and_length() -> None:
    g = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="rpoB",
        organism_id=uuid.uuid4(),
        genomic_accession="NC_000962.3",
        genomic_start=759807,
        genomic_end=763325,
        genomic_strand="+",
        assembly="ASM19595v2",
    )
    assert g.genomic_accession == "NC_000962.3"
    assert g.genomic_strand == "+"
    assert g.length_bp == 763325 - 759807 + 1


def test_gene_length_bp_none_when_coords_missing() -> None:
    g = Gene.create(workspace_id=SHARED_WORKSPACE_ID, primary_name="x", organism_id=uuid.uuid4())
    assert g.length_bp is None


def test_gene_holds_annotations_and_update_replaces_them() -> None:
    from protcellar.domain.protein_catalog.gene_annotation import (
        GeneAnnotation,
        GeneAnnotationAxis,
    )

    g = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="katG", organism_id=uuid.uuid4()
    )
    assert g.annotations == []
    ann = GeneAnnotation(
        axis=GeneAnnotationAxis.VULNERABILITY, key="essentiality", value="non-essential"
    )
    g.update(annotations=[ann])
    assert g.annotations == [ann]
    g.update(genomic_strand="-")
    assert g.genomic_strand == "-"
    assert g.annotations == [ann]  # untouched keys preserved


def test_gene_carries_ordered_locus_names() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="rho",
        organism_id=uuid.uuid4(),
        ordered_locus_names=["Rv1297"],
    )
    assert gene.ordered_locus_names == ["Rv1297"]


def test_gene_ordered_locus_names_default_empty() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="TP53", organism_id=uuid.uuid4()
    )
    assert gene.ordered_locus_names == []


def test_gene_update_ordered_locus_names() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="rho", organism_id=uuid.uuid4()
    )
    gene.update(ordered_locus_names=["Rv1297"])
    assert gene.ordered_locus_names == ["Rv1297"]


def test_gene_carries_orf_names() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name="VPS26",
        organism_id=uuid.uuid4(),
        orf_names=["PF3D7_1250300"],
    )
    assert gene.orf_names == ["PF3D7_1250300"]


def test_gene_orf_names_default_empty() -> None:
    assert (
        Gene.create(
            workspace_id=SHARED_WORKSPACE_ID, primary_name="TP53", organism_id=uuid.uuid4()
        ).orf_names
        == []
    )


def test_gene_update_orf_names() -> None:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID, primary_name="VPS26", organism_id=uuid.uuid4()
    )
    gene.update(orf_names=["PF3D7_1250300"])
    assert gene.orf_names == ["PF3D7_1250300"]


def test_display_label_prefers_locus() -> None:
    # Ordered locus tag wins over both ORF name and symbol.
    assert gene_display_label("rho", ["Rv1297"], ["MTCY373.17"]) == "Rv1297"


def test_display_label_uses_orf_when_no_locus() -> None:
    # Plasmodium: PF3D7 ids are ORF names, not ordered locus names -> ORF leads.
    assert gene_display_label("VPS26", [], ["PF3D7_1250300"]) == "PF3D7_1250300"


def test_display_label_falls_back_to_primary_when_no_locus_or_orf() -> None:
    # Human genes have neither -> symbol wins.
    assert gene_display_label("TP53", [], []) == "TP53"
