"""SQLAlchemy models for the Protein Catalog context."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)
from protcellar.infrastructure.persistence.sqlalchemy.provenance import ProvenanceMixin


class GeneModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin, ProvenanceMixin):
    __tablename__ = "genes"

    primary_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    synonyms: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    ncbi_gene_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ensembl_gene_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hgnc_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)


class ProteinModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin, ProvenanceMixin):
    __tablename__ = "proteins"
    __table_args__ = (
        Index("ix_proteins_primary_accession", "primary_accession", unique=True),
        Index(
            "ix_proteins_secondary_accessions",
            "secondary_accessions",
            postgresql_using="gin",
        ),
    )

    primary_accession: Mapped[str] = mapped_column(String(10), nullable=False)
    secondary_accessions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    entry_name: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    protein_names: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    strain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strains.id"), nullable=True, index=True
    )
    gene_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("genes.id"), nullable=True, index=True
    )
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    seq_length: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    seq_mass: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seq_crc64: Mapped[str | None] = mapped_column(String(16), nullable=True)
    protein_existence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    entry_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequence_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    annotation_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fragment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    uniparc_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    features: Mapped[list[ProteinFeatureModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ProteinFeatureModel.protein_id",
        order_by="ProteinFeatureModel.id",
    )
    comments: Mapped[list[ProteinCommentModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ProteinCommentModel.protein_id",
        order_by="ProteinCommentModel.id",
    )
    isoforms: Mapped[list[ProteinIsoformModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ProteinIsoformModel.protein_id",
        order_by="ProteinIsoformModel.id",
    )
    keyword_refs: Mapped[list[ProteinKeywordModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ProteinKeywordModel.protein_id",
        order_by="ProteinKeywordModel.id",
    )


class ProteinFeatureModel(Base, EntityModelMixin):
    """A positional sequence feature owned by a Protein (UniProt FT line)."""

    __tablename__ = "protein_features"

    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    feature_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_modifier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_modifier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ligand: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    alternative_sequence: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)


class ProteinCommentModel(Base, EntityModelMixin):
    """A general-annotation comment owned by a Protein (UniProt CC block)."""

    __tablename__ = "protein_comments"

    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    comment_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)


class ProteinIsoformModel(Base, EntityModelMixin):
    """An alternative-products isoform owned by a Protein (UniProt -N accession)."""

    __tablename__ = "protein_isoforms"

    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    isoform_accession: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_displayed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sequence: Mapped[str | None] = mapped_column(Text, nullable=True)
    event: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProteinKeywordModel(Base, EntityModelMixin):
    """A UniProt controlled-vocabulary keyword owned by a Protein."""

    __tablename__ = "protein_keywords"

    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    kw_id: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
