"""Gene aggregate — a UniProt GN-line / NCBI Gene (shared reference data)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.protein_catalog.events import GeneCreated, GeneUpdated
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


class Gene(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        primary_name: str,
        organism_id: uuid.UUID,
        strain_id: uuid.UUID | None = None,
        synonyms: list[str] | None = None,
        ordered_locus_names: list[str] | None = None,
        orf_names: list[str] | None = None,
        ncbi_gene_id: str | None = None,
        ensembl_gene_id: str | None = None,
        hgnc_id: str | None = None,
        cross_references: list[CrossReference] | None = None,
        genomic_accession: str | None = None,
        genomic_start: int | None = None,
        genomic_end: int | None = None,
        genomic_strand: str | None = None,
        assembly: str | None = None,
        annotations: list[GeneAnnotation] | None = None,
        source: str | None = None,
        source_release: str | None = None,
        source_record_id: str | None = None,
        source_record_checksum: str | None = None,
        imported_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not primary_name or not primary_name.strip():
            raise ValidationError("Gene primary_name must not be empty")
        # Reference data lives under the reserved GLOBAL workspace.
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.primary_name = primary_name.strip()
        self.organism_id = organism_id
        self.strain_id = strain_id
        self.synonyms = synonyms if synonyms is not None else []
        self.ordered_locus_names = (
            ordered_locus_names if ordered_locus_names is not None else []
        )
        self.orf_names = orf_names if orf_names is not None else []
        self.ncbi_gene_id = ncbi_gene_id
        self.ensembl_gene_id = ensembl_gene_id
        self.hgnc_id = hgnc_id
        self.cross_references = cross_references if cross_references is not None else []
        self.genomic_accession = genomic_accession
        self.genomic_start = genomic_start
        self.genomic_end = genomic_end
        self.genomic_strand = genomic_strand
        self.assembly = assembly
        self.annotations = annotations if annotations is not None else []
        self.source = source
        self.source_release = source_release
        self.source_record_id = source_record_id
        self.source_record_checksum = source_record_checksum
        self.imported_at = imported_at

    @classmethod
    def create(
        cls,
        *,
        primary_name: str,
        organism_id: uuid.UUID,
        strain_id: uuid.UUID | None = None,
        synonyms: list[str] | None = None,
        ordered_locus_names: list[str] | None = None,
        orf_names: list[str] | None = None,
        ncbi_gene_id: str | None = None,
        ensembl_gene_id: str | None = None,
        hgnc_id: str | None = None,
        cross_references: list[CrossReference] | None = None,
        genomic_accession: str | None = None,
        genomic_start: int | None = None,
        genomic_end: int | None = None,
        genomic_strand: str | None = None,
        assembly: str | None = None,
        annotations: list[GeneAnnotation] | None = None,
    ) -> Gene:
        gene = cls(
            primary_name=primary_name,
            organism_id=organism_id,
            strain_id=strain_id,
            synonyms=synonyms,
            ordered_locus_names=ordered_locus_names,
            orf_names=orf_names,
            ncbi_gene_id=ncbi_gene_id,
            ensembl_gene_id=ensembl_gene_id,
            hgnc_id=hgnc_id,
            cross_references=cross_references,
            genomic_accession=genomic_accession,
            genomic_start=genomic_start,
            genomic_end=genomic_end,
            genomic_strand=genomic_strand,
            assembly=assembly,
            annotations=annotations,
        )
        gene.register_event(
            GeneCreated(
                aggregate_id=gene.id,
                aggregate_type="Gene",
                workspace_id=gene.workspace_id,
                primary_name=gene.primary_name,
                organism_id=gene.organism_id,
            )
        )
        return gene

    @property
    def length_bp(self) -> int | None:
        if self.genomic_start is None or self.genomic_end is None:
            return None
        return self.genomic_end - self.genomic_start + 1

    def update(self, **fields: Any) -> None:
        if "primary_name" in fields:
            value = fields["primary_name"]
            if not value or not str(value).strip():
                raise ValidationError("Gene primary_name must not be empty")
            self.primary_name = str(value).strip()
        if "synonyms" in fields:
            self.synonyms = list(fields["synonyms"] or [])
        if "ordered_locus_names" in fields:
            self.ordered_locus_names = list(fields["ordered_locus_names"] or [])
        if "orf_names" in fields:
            self.orf_names = list(fields["orf_names"] or [])
        if "ncbi_gene_id" in fields:
            self.ncbi_gene_id = fields["ncbi_gene_id"]
        if "ensembl_gene_id" in fields:
            self.ensembl_gene_id = fields["ensembl_gene_id"]
        if "hgnc_id" in fields:
            self.hgnc_id = fields["hgnc_id"]
        if "strain_id" in fields:
            self.strain_id = fields["strain_id"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
        for _loc in (
            "genomic_accession",
            "genomic_start",
            "genomic_end",
            "genomic_strand",
            "assembly",
        ):
            if _loc in fields:
                setattr(self, _loc, fields[_loc])
        if "annotations" in fields:
            self.annotations = list(fields["annotations"] or [])
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            GeneUpdated(
                aggregate_id=self.id,
                aggregate_type="Gene",
                workspace_id=self.workspace_id,
            )
        )


def gene_display_label(
    primary_name: str, ordered_locus_names: list[str], orf_names: list[str]
) -> str:
    """Gene-context label: the ordered locus tag (Rv1066), else the ORF name
    (PF3D7_0216700 for Plasmodium, whose loci UniProt files as ORF names), else the
    primary name. Protein-context views keep the symbol (primary_name)."""
    # ponytail: first locus/ORF wins; a multi-strain gene may list Rv#### + MT#### — a
    # strain-aware pick needs a strain->prefix map, defer until a view needs it.
    if ordered_locus_names:
        return ordered_locus_names[0]
    if orf_names:
        return orf_names[0]
    return primary_name
