"""SQLAlchemy Protein repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._xref_json import (
    xrefs_from_json,
    xrefs_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import ProteinModel


class SQLAlchemyProteinRepository(SQLAlchemyRepository[Protein, ProteinModel], ProteinRepository):
    model_class = ProteinModel

    def _to_domain(self, model: ProteinModel) -> Protein:
        return Protein(
            id=model.id,
            primary_accession=model.primary_accession,
            organism_id=model.organism_id,
            sequence=model.sequence,
            is_reviewed=model.is_reviewed,
            secondary_accessions=(
                list(model.secondary_accessions) if model.secondary_accessions else []
            ),
            entry_name=model.entry_name,
            protein_names=ProteinNames.from_dict(model.protein_names),
            strain_id=model.strain_id,
            gene_id=model.gene_id,
            seq_mass=model.seq_mass,
            seq_crc64=model.seq_crc64,
            protein_existence=(
                ProteinExistence(model.protein_existence)
                if model.protein_existence is not None
                else None
            ),
            keywords=list(model.keywords) if model.keywords else [],
            entry_version=model.entry_version,
            sequence_version=model.sequence_version,
            cross_references=xrefs_from_json(model.cross_references),
            annotation_score=model.annotation_score,
            fragment=model.fragment,
            uniparc_id=model.uniparc_id,
            source=model.source,
            source_release=model.source_release,
            source_record_id=model.source_record_id,
            source_record_checksum=model.source_record_checksum,
            imported_at=model.imported_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Protein) -> ProteinModel:
        return ProteinModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            primary_accession=aggregate.primary_accession,
            secondary_accessions=aggregate.secondary_accessions or None,
            entry_name=aggregate.entry_name,
            is_reviewed=aggregate.is_reviewed,
            protein_names=aggregate.protein_names.to_dict(),
            organism_id=aggregate.organism_id,
            strain_id=aggregate.strain_id,
            gene_id=aggregate.gene_id,
            sequence=aggregate.sequence,
            seq_length=aggregate.seq_length,
            seq_mass=aggregate.seq_mass,
            seq_crc64=aggregate.seq_crc64,
            protein_existence=(
                aggregate.protein_existence.value
                if aggregate.protein_existence is not None
                else None
            ),
            keywords=aggregate.keywords or None,
            entry_version=aggregate.entry_version,
            sequence_version=aggregate.sequence_version,
            cross_references=xrefs_to_json(aggregate.cross_references) or None,
            annotation_score=aggregate.annotation_score,
            fragment=aggregate.fragment,
            uniparc_id=aggregate.uniparc_id,
            source=aggregate.source,
            source_release=aggregate.source_release,
            source_record_id=aggregate.source_record_id,
            source_record_checksum=aggregate.source_record_checksum,
            imported_at=aggregate.imported_at,
            version=aggregate.version,
        )

    def _update_model(self, model: ProteinModel, aggregate: Protein) -> None:
        model.primary_accession = aggregate.primary_accession
        model.secondary_accessions = aggregate.secondary_accessions or None
        model.entry_name = aggregate.entry_name
        model.is_reviewed = aggregate.is_reviewed
        model.protein_names = aggregate.protein_names.to_dict()
        model.organism_id = aggregate.organism_id
        model.strain_id = aggregate.strain_id
        model.gene_id = aggregate.gene_id
        model.sequence = aggregate.sequence
        model.seq_length = aggregate.seq_length
        model.seq_mass = aggregate.seq_mass
        model.seq_crc64 = aggregate.seq_crc64
        model.protein_existence = (
            aggregate.protein_existence.value if aggregate.protein_existence is not None else None
        )
        model.keywords = aggregate.keywords or None
        model.entry_version = aggregate.entry_version
        model.sequence_version = aggregate.sequence_version
        model.cross_references = xrefs_to_json(aggregate.cross_references) or None
        model.annotation_score = aggregate.annotation_score
        model.fragment = aggregate.fragment
        model.uniparc_id = aggregate.uniparc_id
        model.source = aggregate.source
        model.source_release = aggregate.source_release
        model.source_record_id = aggregate.source_record_id
        model.source_record_checksum = aggregate.source_record_checksum
        model.imported_at = aggregate.imported_at

    async def find_by_accession(self, accession: str) -> Protein | None:
        # Primary first, then secondary (resolves merged/demerged accessions).
        stmt = select(ProteinModel).where(ProteinModel.primary_accession == accession)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            # `@>` array-containment so the GIN index on secondary_accessions is usable.
            stmt = select(ProteinModel).where(
                ProteinModel.secondary_accessions.contains([accession])
            )
            model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_entry_name(self, entry_name: str) -> Protein | None:
        stmt = select(ProteinModel).where(ProteinModel.entry_name == entry_name)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_source_record_id(self, source: str, source_record_id: str) -> Protein | None:
        stmt = select(ProteinModel).where(
            ProteinModel.source == source,
            ProteinModel.source_record_id == source_record_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        is_reviewed: bool | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> list[Protein]:
        stmt = select(ProteinModel).order_by(ProteinModel.id)
        if organism_id is not None:
            stmt = stmt.where(ProteinModel.organism_id == organism_id)
        if gene_id is not None:
            stmt = stmt.where(ProteinModel.gene_id == gene_id)
        if is_reviewed is not None:
            stmt = stmt.where(ProteinModel.is_reviewed == is_reviewed)
        if min_length is not None:
            stmt = stmt.where(ProteinModel.seq_length >= min_length)
        if max_length is not None:
            stmt = stmt.where(ProteinModel.seq_length <= max_length)
        if cursor_id is not None:
            stmt = stmt.where(ProteinModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
