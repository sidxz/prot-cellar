"""SQLAlchemy Gene repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._annotation_json import (
    annotations_from_json,
    annotations_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._xref_json import (
    xrefs_from_json,
    xrefs_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import GeneModel


class SQLAlchemyGeneRepository(SQLAlchemyRepository[Gene, GeneModel], GeneRepository):
    model_class = GeneModel

    def _to_domain(self, model: GeneModel) -> Gene:
        return Gene(
            id=model.id,
            primary_name=model.primary_name,
            organism_id=model.organism_id,
            synonyms=list(model.synonyms) if model.synonyms else [],
            ncbi_gene_id=model.ncbi_gene_id,
            ensembl_gene_id=model.ensembl_gene_id,
            hgnc_id=model.hgnc_id,
            cross_references=xrefs_from_json(model.cross_references),
            genomic_accession=model.genomic_accession,
            genomic_start=model.genomic_start,
            genomic_end=model.genomic_end,
            genomic_strand=model.genomic_strand,
            assembly=model.assembly,
            annotations=annotations_from_json(model.annotations),
            source=model.source,
            source_release=model.source_release,
            source_record_id=model.source_record_id,
            source_record_checksum=model.source_record_checksum,
            imported_at=model.imported_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Gene) -> GeneModel:
        return GeneModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            primary_name=aggregate.primary_name,
            organism_id=aggregate.organism_id,
            synonyms=aggregate.synonyms or None,
            ncbi_gene_id=aggregate.ncbi_gene_id,
            ensembl_gene_id=aggregate.ensembl_gene_id,
            hgnc_id=aggregate.hgnc_id,
            cross_references=xrefs_to_json(aggregate.cross_references) or None,
            genomic_accession=aggregate.genomic_accession,
            genomic_start=aggregate.genomic_start,
            genomic_end=aggregate.genomic_end,
            genomic_strand=aggregate.genomic_strand,
            assembly=aggregate.assembly,
            annotations=annotations_to_json(aggregate.annotations) or None,
            source=aggregate.source,
            source_release=aggregate.source_release,
            source_record_id=aggregate.source_record_id,
            source_record_checksum=aggregate.source_record_checksum,
            imported_at=aggregate.imported_at,
            version=aggregate.version,
        )

    def _update_model(self, model: GeneModel, aggregate: Gene) -> None:
        model.primary_name = aggregate.primary_name
        model.organism_id = aggregate.organism_id
        model.synonyms = aggregate.synonyms or None
        model.ncbi_gene_id = aggregate.ncbi_gene_id
        model.ensembl_gene_id = aggregate.ensembl_gene_id
        model.hgnc_id = aggregate.hgnc_id
        model.cross_references = xrefs_to_json(aggregate.cross_references) or None
        model.genomic_accession = aggregate.genomic_accession
        model.genomic_start = aggregate.genomic_start
        model.genomic_end = aggregate.genomic_end
        model.genomic_strand = aggregate.genomic_strand
        model.assembly = aggregate.assembly
        model.annotations = annotations_to_json(aggregate.annotations) or None
        model.source = aggregate.source
        model.source_release = aggregate.source_release
        model.source_record_id = aggregate.source_record_id
        model.source_record_checksum = aggregate.source_record_checksum
        model.imported_at = aggregate.imported_at

    async def find_by_ids(self, ids: Sequence[uuid.UUID]) -> list[Gene]:
        if not ids:
            return []
        stmt = select(GeneModel).where(GeneModel.id.in_(list(ids)))
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_by_name(self, name: str, organism_id: uuid.UUID | None = None) -> list[Gene]:
        stmt = select(GeneModel).where(GeneModel.primary_name.ilike(f"%{name}%"))
        if organism_id is not None:
            stmt = stmt.where(GeneModel.organism_id == organism_id)
        stmt = stmt.order_by(GeneModel.primary_name).limit(50)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_by_ncbi_gene_id(self, ncbi_gene_id: str) -> Gene | None:
        stmt = select(GeneModel).where(GeneModel.ncbi_gene_id == ncbi_gene_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_source_record_id(self, source: str, source_record_id: str) -> Gene | None:
        stmt = select(GeneModel).where(
            GeneModel.source == source,
            GeneModel.source_record_id == source_record_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
    ) -> list[Gene]:
        stmt = select(GeneModel).order_by(GeneModel.id)
        if organism_id is not None:
            stmt = stmt.where(GeneModel.organism_id == organism_id)
        if cursor_id is not None:
            stmt = stmt.where(GeneModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
