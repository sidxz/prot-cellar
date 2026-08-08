"""Protein aggregate — a UniProtKB entry (shared reference data; heart of the catalog)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.events import ProteinCreated, ProteinUpdated
from protcellar.domain.protein_catalog.value_objects import (
    ProteinCitation,
    ProteinComment,
    ProteinFeature,
    ProteinIsoform,
    ProteinKeyword,
    ProteinNames,
)
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError

# UniProtKB accession syntax (6 or 10 alphanumerics, two layouts). Mirrors the
# registry `uniprot` prefix but kept here so the domain stays dependency-free.
_UNIPROT_ACCESSION_RE: re.Pattern[str] = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

_FASTA_WIDTH = 60


class Protein(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        primary_accession: str,
        organism_id: uuid.UUID,
        sequence: str,
        is_reviewed: bool,
        secondary_accessions: list[str] | None = None,
        entry_name: str | None = None,
        protein_names: ProteinNames | None = None,
        strain_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        seq_mass: int | None = None,
        seq_crc64: str | None = None,
        protein_existence: ProteinExistence | None = None,
        keywords: list[str] | None = None,
        entry_version: int | None = None,
        sequence_version: int | None = None,
        cross_references: list[CrossReference] | None = None,
        annotation_score: int | None = None,
        fragment: str | None = None,
        uniparc_id: str | None = None,
        features: list[ProteinFeature] | None = None,
        comments: list[ProteinComment] | None = None,
        isoforms: list[ProteinIsoform] | None = None,
        keyword_refs: list[ProteinKeyword] | None = None,
        citations: list[ProteinCitation] | None = None,
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
        accession = (primary_accession or "").strip()
        if not _UNIPROT_ACCESSION_RE.match(accession):
            raise ValidationError(f"Invalid UniProt primary_accession '{primary_accession}'")
        if not sequence or not sequence.strip():
            raise ValidationError("Protein sequence must not be empty")
        self.workspace_id = workspace_id
        self.primary_accession = accession
        self.organism_id = organism_id
        self.sequence = sequence.strip()
        self.seq_length = len(self.sequence)
        self.is_reviewed = is_reviewed
        self.secondary_accessions = (
            secondary_accessions if secondary_accessions is not None else []
        )
        self.entry_name = entry_name
        self.protein_names = protein_names if protein_names is not None else ProteinNames()
        self.strain_id = strain_id
        self.gene_id = gene_id
        self.seq_mass = seq_mass
        self.seq_crc64 = seq_crc64
        self.protein_existence = protein_existence
        self.keywords = keywords if keywords is not None else []
        self.entry_version = entry_version
        self.sequence_version = sequence_version
        self.cross_references = cross_references if cross_references is not None else []
        self.annotation_score = annotation_score
        self.fragment = fragment
        self.uniparc_id = uniparc_id
        self.features = features if features is not None else []
        self.comments = comments if comments is not None else []
        self.isoforms = isoforms if isoforms is not None else []
        self.keyword_refs = keyword_refs if keyword_refs is not None else []
        self.citations = citations if citations is not None else []
        self.source = source
        self.source_release = source_release
        self.source_record_id = source_record_id
        self.source_record_checksum = source_record_checksum
        self.imported_at = imported_at

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        primary_accession: str,
        organism_id: uuid.UUID,
        sequence: str,
        is_reviewed: bool,
        secondary_accessions: list[str] | None = None,
        entry_name: str | None = None,
        protein_names: ProteinNames | None = None,
        strain_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        seq_mass: int | None = None,
        seq_crc64: str | None = None,
        protein_existence: ProteinExistence | None = None,
        keywords: list[str] | None = None,
        entry_version: int | None = None,
        sequence_version: int | None = None,
        cross_references: list[CrossReference] | None = None,
        annotation_score: int | None = None,
        fragment: str | None = None,
        uniparc_id: str | None = None,
        features: list[ProteinFeature] | None = None,
        comments: list[ProteinComment] | None = None,
        isoforms: list[ProteinIsoform] | None = None,
        keyword_refs: list[ProteinKeyword] | None = None,
        citations: list[ProteinCitation] | None = None,
    ) -> Protein:
        protein = cls(
            workspace_id=workspace_id,
            primary_accession=primary_accession,
            organism_id=organism_id,
            sequence=sequence,
            is_reviewed=is_reviewed,
            secondary_accessions=secondary_accessions,
            entry_name=entry_name,
            protein_names=protein_names,
            strain_id=strain_id,
            gene_id=gene_id,
            seq_mass=seq_mass,
            seq_crc64=seq_crc64,
            protein_existence=protein_existence,
            keywords=keywords,
            entry_version=entry_version,
            sequence_version=sequence_version,
            cross_references=cross_references,
            annotation_score=annotation_score,
            fragment=fragment,
            uniparc_id=uniparc_id,
            features=features,
            comments=comments,
            isoforms=isoforms,
            keyword_refs=keyword_refs,
            citations=citations,
        )
        protein.register_event(
            ProteinCreated(
                aggregate_id=protein.id,
                aggregate_type="Protein",
                workspace_id=protein.workspace_id,
                primary_accession=protein.primary_accession,
                organism_id=protein.organism_id,
            )
        )
        return protein

    def update(self, **fields: Any) -> None:
        if "sequence" in fields:
            value = str(fields["sequence"] or "").strip()
            if not value:
                raise ValidationError("Protein sequence must not be empty")
            self.sequence = value
            self.seq_length = len(value)
        if "is_reviewed" in fields:
            self.is_reviewed = bool(fields["is_reviewed"])
        if "entry_name" in fields:
            self.entry_name = fields["entry_name"]
        if "protein_names" in fields:
            self.protein_names = fields["protein_names"] or ProteinNames()
        if "secondary_accessions" in fields:
            self.secondary_accessions = list(fields["secondary_accessions"] or [])
        if "strain_id" in fields:
            self.strain_id = fields["strain_id"]
        if "gene_id" in fields:
            self.gene_id = fields["gene_id"]
        if "seq_mass" in fields:
            self.seq_mass = fields["seq_mass"]
        if "seq_crc64" in fields:
            self.seq_crc64 = fields["seq_crc64"]
        if "protein_existence" in fields:
            self.protein_existence = fields["protein_existence"]
        if "keywords" in fields:
            self.keywords = list(fields["keywords"] or [])
        if "entry_version" in fields:
            self.entry_version = fields["entry_version"]
        if "sequence_version" in fields:
            self.sequence_version = fields["sequence_version"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
        if "annotation_score" in fields:
            self.annotation_score = fields["annotation_score"]
        if "fragment" in fields:
            self.fragment = fields["fragment"]
        if "uniparc_id" in fields:
            self.uniparc_id = fields["uniparc_id"]
        if "features" in fields:
            self.features = list(fields["features"] or [])
        if "comments" in fields:
            self.comments = list(fields["comments"] or [])
        if "isoforms" in fields:
            self.isoforms = list(fields["isoforms"] or [])
        if "keyword_refs" in fields:
            self.keyword_refs = list(fields["keyword_refs"] or [])
        if "citations" in fields:
            self.citations = list(fields["citations"] or [])
        self._touch()

    def to_fasta(self) -> str:
        """Render a (simplified) UniProt-style FASTA record from local fields."""
        db = "sp" if self.is_reviewed else "tr"
        header = f">{db}|{self.primary_accession}|{self.entry_name or self.primary_accession}"
        display = self.protein_names.display_name
        if display:
            header += f" {display}"
        if self.protein_existence is not None:
            header += f" PE={self.protein_existence.level}"
        if self.sequence_version is not None:
            header += f" SV={self.sequence_version}"
        wrapped = [
            self.sequence[i : i + _FASTA_WIDTH] for i in range(0, len(self.sequence), _FASTA_WIDTH)
        ]
        return "\n".join([header, *wrapped])

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            ProteinUpdated(
                aggregate_id=self.id,
                aggregate_type="Protein",
                workspace_id=self.workspace_id,
            )
        )
