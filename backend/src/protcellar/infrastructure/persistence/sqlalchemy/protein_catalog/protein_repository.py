"""SQLAlchemy Protein repository."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, select

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.protein_catalog.value_objects import (
    ProteinCitation,
    ProteinComment,
    ProteinFeature,
    ProteinIsoform,
    ProteinKeyword,
    ProteinNames,
)
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import (
    ProteinCitationModel,
    ProteinCommentModel,
    ProteinCrossReferenceModel,
    ProteinFeatureModel,
    ProteinIsoformModel,
    ProteinKeywordModel,
    ProteinModel,
)

_STRUCTURE_DBS = ("PDB", "PDBsum", "AlphaFoldDB", "EMDB", "SMR")


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
            cross_references=[
                CrossReference(
                    database=x.database,
                    accession=x.accession,
                    properties=x.properties,
                    evidence=x.evidence,
                )
                for x in model.cross_reference_rows
            ],
            annotation_score=model.annotation_score,
            fragment=model.fragment,
            uniparc_id=model.uniparc_id,
            features=[
                ProteinFeature(
                    id=f.id,
                    feature_type=f.feature_type,
                    start=f.start_pos,
                    end=f.end_pos,
                    start_modifier=f.start_modifier,
                    end_modifier=f.end_modifier,
                    description=f.description,
                    feature_id=f.feature_id,
                    ligand=f.ligand,
                    alternative_sequence=f.alternative_sequence,
                    evidence=f.evidence,
                )
                for f in model.features
            ],
            comments=[
                ProteinComment(
                    id=c.id,
                    comment_type=c.comment_type,
                    text=c.text,
                    payload=c.payload,
                    evidence=c.evidence,
                )
                for c in model.comments
            ],
            isoforms=[
                ProteinIsoform(
                    id=i.id,
                    isoform_accession=i.isoform_accession,
                    name=i.name,
                    is_displayed=i.is_displayed,
                    sequence=i.sequence,
                    event=i.event,
                    note=i.note,
                )
                for i in model.isoforms
            ],
            keyword_refs=[
                ProteinKeyword(
                    id=k.id,
                    kw_id=k.kw_id,
                    name=k.name,
                    category=k.category,
                )
                for k in model.keyword_refs
            ],
            citations=[
                ProteinCitation(
                    id=ct.id,
                    citation_type=ct.citation_type,
                    title=ct.title,
                    journal=ct.journal,
                    authors=ct.authors,
                    publication_date=ct.publication_date,
                    pubmed_id=ct.pubmed_id,
                    doi=ct.doi,
                    reference_number=ct.reference_number,
                    positions=ct.positions,
                    reference_comments=ct.reference_comments,
                )
                for ct in model.citations
            ],
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
        model = ProteinModel(
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
        model.features = [self._feature_to_model(f) for f in aggregate.features]
        model.comments = [self._comment_to_model(c) for c in aggregate.comments]
        model.isoforms = [self._isoform_to_model(i) for i in aggregate.isoforms]
        model.keyword_refs = [self._keyword_to_model(k) for k in aggregate.keyword_refs]
        model.citations = [self._citation_to_model(ct) for ct in aggregate.citations]
        model.cross_reference_rows = [self._xref_to_model(x) for x in aggregate.cross_references]
        return model

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
        model.cross_reference_rows = [self._xref_to_model(x) for x in aggregate.cross_references]
        model.annotation_score = aggregate.annotation_score
        model.fragment = aggregate.fragment
        model.uniparc_id = aggregate.uniparc_id
        model.features = [self._feature_to_model(f) for f in aggregate.features]
        model.comments = [self._comment_to_model(c) for c in aggregate.comments]
        model.isoforms = [self._isoform_to_model(i) for i in aggregate.isoforms]
        model.keyword_refs = [self._keyword_to_model(k) for k in aggregate.keyword_refs]
        model.citations = [self._citation_to_model(ct) for ct in aggregate.citations]
        model.source = aggregate.source
        model.source_release = aggregate.source_release
        model.source_record_id = aggregate.source_record_id
        model.source_record_checksum = aggregate.source_record_checksum
        model.imported_at = aggregate.imported_at

    @staticmethod
    def _feature_to_model(f: ProteinFeature) -> ProteinFeatureModel:
        return ProteinFeatureModel(
            id=f.id,
            feature_type=f.feature_type,
            start_pos=f.start,
            end_pos=f.end,
            start_modifier=f.start_modifier,
            end_modifier=f.end_modifier,
            description=f.description,
            feature_id=f.feature_id,
            ligand=f.ligand,
            alternative_sequence=f.alternative_sequence,
            evidence=f.evidence,
        )

    @staticmethod
    def _comment_to_model(c: ProteinComment) -> ProteinCommentModel:
        return ProteinCommentModel(
            id=c.id,
            comment_type=c.comment_type,
            text=c.text,
            payload=c.payload,
            evidence=c.evidence,
        )

    @staticmethod
    def _isoform_to_model(i: ProteinIsoform) -> ProteinIsoformModel:
        return ProteinIsoformModel(
            id=i.id,
            isoform_accession=i.isoform_accession,
            name=i.name,
            is_displayed=i.is_displayed,
            sequence=i.sequence,
            event=i.event,
            note=i.note,
        )

    @staticmethod
    def _keyword_to_model(k: ProteinKeyword) -> ProteinKeywordModel:
        return ProteinKeywordModel(
            id=k.id,
            kw_id=k.kw_id,
            name=k.name,
            category=k.category,
        )

    @staticmethod
    def _citation_to_model(ct: ProteinCitation) -> ProteinCitationModel:
        return ProteinCitationModel(
            id=ct.id,
            citation_type=ct.citation_type,
            title=ct.title,
            journal=ct.journal,
            authors=ct.authors,
            publication_date=ct.publication_date,
            pubmed_id=ct.pubmed_id,
            doi=ct.doi,
            reference_number=ct.reference_number,
            positions=ct.positions,
            reference_comments=ct.reference_comments,
        )

    @staticmethod
    def _xref_to_model(x: CrossReference) -> ProteinCrossReferenceModel:
        return ProteinCrossReferenceModel(
            database=x.database,
            accession=x.accession,
            properties=x.properties,
            evidence=x.evidence,
        )

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
        xref_db: str | None = None,
        has_structure: bool | None = None,
        go_terms: list[str] | None = None,
        keyword: str | None = None,
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
        if xref_db is not None:
            stmt = stmt.where(
                exists().where(
                    ProteinCrossReferenceModel.protein_id == ProteinModel.id,
                    ProteinCrossReferenceModel.database == xref_db,
                )
            )
        if has_structure:
            stmt = stmt.where(
                exists().where(
                    ProteinCrossReferenceModel.protein_id == ProteinModel.id,
                    ProteinCrossReferenceModel.database.in_(_STRUCTURE_DBS),
                )
            )
        if go_terms:
            stmt = stmt.where(
                exists().where(
                    ProteinCrossReferenceModel.protein_id == ProteinModel.id,
                    ProteinCrossReferenceModel.database == "GO",
                    ProteinCrossReferenceModel.accession.in_(go_terms),
                )
            )
        if keyword is not None:
            stmt = stmt.where(
                exists().where(
                    ProteinKeywordModel.protein_id == ProteinModel.id,
                    ProteinKeywordModel.kw_id == keyword,
                )
            )
        if cursor_id is not None:
            stmt = stmt.where(ProteinModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
