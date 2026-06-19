"""Gene aggregate — a UniProt GN-line / NCBI Gene (shared reference data)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.protein_catalog.events import GeneCreated, GeneUpdated
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
        synonyms: list[str] | None = None,
        ncbi_gene_id: str | None = None,
        ensembl_gene_id: str | None = None,
        hgnc_id: str | None = None,
        cross_references: list[CrossReference] | None = None,
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
        self.synonyms = synonyms if synonyms is not None else []
        self.ncbi_gene_id = ncbi_gene_id
        self.ensembl_gene_id = ensembl_gene_id
        self.hgnc_id = hgnc_id
        self.cross_references = cross_references if cross_references is not None else []
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
        synonyms: list[str] | None = None,
        ncbi_gene_id: str | None = None,
        ensembl_gene_id: str | None = None,
        hgnc_id: str | None = None,
        cross_references: list[CrossReference] | None = None,
    ) -> Gene:
        gene = cls(
            primary_name=primary_name,
            organism_id=organism_id,
            synonyms=synonyms,
            ncbi_gene_id=ncbi_gene_id,
            ensembl_gene_id=ensembl_gene_id,
            hgnc_id=hgnc_id,
            cross_references=cross_references,
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

    def update(self, **fields: Any) -> None:
        if "primary_name" in fields:
            value = fields["primary_name"]
            if not value or not str(value).strip():
                raise ValidationError("Gene primary_name must not be empty")
            self.primary_name = str(value).strip()
        if "synonyms" in fields:
            self.synonyms = list(fields["synonyms"] or [])
        if "ncbi_gene_id" in fields:
            self.ncbi_gene_id = fields["ncbi_gene_id"]
        if "ensembl_gene_id" in fields:
            self.ensembl_gene_id = fields["ensembl_gene_id"]
        if "hgnc_id" in fields:
            self.hgnc_id = fields["hgnc_id"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
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
