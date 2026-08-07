"""SQLAlchemy Gene repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.read_models import GeneSummaryRow
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
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import GeneTagLinkModel
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_filter import tag_filter_subquery


class SQLAlchemyGeneRepository(SQLAlchemyRepository[Gene, GeneModel], GeneRepository):
    model_class = GeneModel

    def _to_domain(self, model: GeneModel) -> Gene:
        return Gene(
            id=model.id,
            primary_name=model.primary_name,
            organism_id=model.organism_id,
            strain_id=model.strain_id,
            synonyms=list(model.synonyms) if model.synonyms else [],
            ordered_locus_names=(
                list(model.ordered_locus_names) if model.ordered_locus_names else []
            ),
            orf_names=list(model.orf_names) if model.orf_names else [],
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
            strain_id=aggregate.strain_id,
            synonyms=aggregate.synonyms or None,
            ordered_locus_names=aggregate.ordered_locus_names or None,
            orf_names=aggregate.orf_names or None,
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
        model.strain_id = aggregate.strain_id
        model.synonyms = aggregate.synonyms or None
        model.ordered_locus_names = aggregate.ordered_locus_names or None
        model.orf_names = aggregate.orf_names or None
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

    async def find_summary_rows_by_ids(self, ids: Sequence[uuid.UUID]) -> list[GeneSummaryRow]:
        # Column select only (see GeneSummaryRow): no aggregate hydration, no tracking.
        if not ids:
            return []
        stmt = select(
            GeneModel.id,
            GeneModel.primary_name,
            GeneModel.synonyms,
            GeneModel.ordered_locus_names,
            GeneModel.orf_names,
        ).where(GeneModel.id.in_(list(ids)))
        return [
            GeneSummaryRow(
                id=row.id,
                primary_name=row.primary_name,
                synonyms=list(row.synonyms) if row.synonyms else [],
                ordered_locus_names=(
                    list(row.ordered_locus_names) if row.ordered_locus_names else []
                ),
                orf_names=list(row.orf_names) if row.orf_names else [],
            )
            for row in await self._session.execute(stmt)
        ]

    async def find_by_name(
        self,
        name: str,
        organism_id: uuid.UUID | None = None,
        strain_id: uuid.UUID | None = None,
    ) -> list[Gene]:
        stmt = select(GeneModel).where(GeneModel.primary_name.ilike(f"%{name}%"))
        if organism_id is not None:
            stmt = stmt.where(GeneModel.organism_id == organism_id)
        if strain_id is not None:
            stmt = stmt.where(GeneModel.strain_id == strain_id)
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

    async def list_by_organism(self, organism_id: uuid.UUID, *, batch: int = 1000) -> list[Gene]:
        """Load every gene for an organism, paged by keyset (``id``) in ``batch``-sized chunks.

        Used to build the locus→gene match index for enrichment; the keyset walk
        keeps memory bounded per query while still returning the full set.
        """
        genes: list[Gene] = []
        cursor: uuid.UUID | None = None
        while True:
            stmt = select(GeneModel).where(GeneModel.organism_id == organism_id)
            if cursor is not None:
                stmt = stmt.where(GeneModel.id > cursor)
            stmt = stmt.order_by(GeneModel.id).limit(batch)
            page = [
                self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()
            ]
            if not page:
                break
            genes.extend(page)
            if len(page) < batch:
                break
            cursor = page[-1].id
        return genes

    async def find_genomic_neighbors(
        self,
        *,
        organism_id: uuid.UUID,
        genomic_accession: str,
        center_start: int,
        window: int,
    ) -> list[Gene]:
        """Return genes flanking ``center_start`` on the same replicon.

        Two bounded queries (``window`` upstream, ``window`` downstream incl.
        the center gene) are merged and re-sorted, so the whole replicon never
        has to be loaded. Result is ascending by ``genomic_start``.
        """
        base = (GeneModel.organism_id == organism_id) & (
            GeneModel.genomic_accession == genomic_accession
        )
        upstream = (
            select(GeneModel)
            .where(base, GeneModel.genomic_start < center_start)
            .order_by(GeneModel.genomic_start.desc())
            .limit(window)
        )
        downstream = (
            select(GeneModel)
            .where(base, GeneModel.genomic_start >= center_start)
            .order_by(GeneModel.genomic_start.asc())
            .limit(window + 1)  # +1 includes the center gene itself
        )
        rows = list((await self._session.execute(upstream)).scalars()) + list(
            (await self._session.execute(downstream)).scalars()
        )
        rows.sort(key=lambda m: m.genomic_start if m.genomic_start is not None else 0)
        return [self._to_domain_tracked(m) for m in rows]

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
        strain_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        tag_ids: list[uuid.UUID] | None = None,
        match_all: bool = False,
    ) -> list[Gene]:
        stmt = select(GeneModel).order_by(GeneModel.id)
        if organism_id is not None:
            stmt = stmt.where(GeneModel.organism_id == organism_id)
        if strain_id is not None:
            stmt = stmt.where(GeneModel.strain_id == strain_id)
        if tag_ids:
            stmt = stmt.where(
                GeneModel.id.in_(
                    tag_filter_subquery(
                        GeneTagLinkModel,
                        "gene_id",
                        tag_ids,
                        workspace_id=workspace_id,
                        match_all=match_all,
                    )
                )
            )
        if cursor_id is not None:
            stmt = stmt.where(GeneModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
