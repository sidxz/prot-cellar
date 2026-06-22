"""SQLAlchemy models for the taxonomy context."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)
from protcellar.infrastructure.persistence.sqlalchemy.provenance import ProvenanceMixin


class OrganismModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "organisms"

    ncbi_tax_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, unique=True, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True, index=True
    )
    rank: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scientific_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    division: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_merged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Import provenance (Organism reuses `source` as the provenance source;
    # ProvenanceMixin not used due to name clash).
    source_release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_record_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    names: Mapped[list[OrganismNameModel]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", foreign_keys="OrganismNameModel.organism_id"
    )


class StrainModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "strains"

    species_organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    ncbi_taxon_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    isolate: Mapped[str | None] = mapped_column(String(256), nullable=True)
    biosample_acc: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    assembly_acc: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    culture_collection: Mapped[str | None] = mapped_column(String(128), nullable=True)
    host_organism_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True
    )
    strain_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class OrganismNameModel(Base, EntityModelMixin):
    __tablename__ = "organism_names"
    __table_args__ = (UniqueConstraint("organism_id", "name_class", "name", name="uq_orgname"),)

    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    name_class: Mapped[str] = mapped_column(String(32), nullable=False)
    unique_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProteomeModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin, ProvenanceMixin):
    __tablename__ = "proteomes"
    __table_args__ = (
        Index("ix_proteomes_uniprot_proteome_id", "uniprot_proteome_id", unique=True),
    )

    uniprot_proteome_id: Mapped[str] = mapped_column(String(16), nullable=False)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisms.id"), nullable=False, index=True
    )
    strain_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strains.id"), nullable=True, index=True
    )
    proteome_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_reference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assembly_acc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ProteomeProteinModel(Base, EntityModelMixin):
    """Membership link between a Proteome and a Protein (shared reference data)."""

    __tablename__ = "proteome_proteins"
    __table_args__ = (UniqueConstraint("proteome_id", "protein_id", name="uq_proteome_protein"),)

    proteome_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteomes.id"), nullable=False, index=True
    )
    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
