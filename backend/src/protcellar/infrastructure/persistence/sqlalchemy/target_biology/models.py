"""SQLAlchemy models for the target_biology context.

gene_id / target_gene_id are bare indexed UUIDs, NOT DB foreign keys: these
aggregates reference genes by identity across a bounded-context boundary, so
referential integrity is the application's responsibility (matches the
"contexts are independent" rule and keeps their lifecycles decoupled).
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Float, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class EssentialityRecordModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "essentiality_records"

    gene_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    condition: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    # ponytail: JSON (not JSONB) to match existing columns; promote to JSONB when
    # the deferred extensions registry makes this queryable.
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class CrispriStrainModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "crispri_strains"

    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    target_gene_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class VulnerabilityRecordModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "vulnerability_records"

    gene_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    condition: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    vulnerability_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class HypomorphModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "hypomorphs"

    gene_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    growth_defect: Mapped[bool] = mapped_column(Boolean, nullable=False)
    knockdown_strain_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    growth_defect_severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class ResistanceMutationModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "resistance_mutations"

    gene_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    mutation: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    compound: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    mic_shift: Mapped[float | None] = mapped_column(Float, nullable=True)
    parent_strain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protein_coordinate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class ProteinProductionModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "protein_productions"

    protein_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expression_host: Mapped[str | None] = mapped_column(String(128), nullable=True)
    purity: Mapped[float | None] = mapped_column(Float, nullable=True)
    condition: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class ProteinActivityAssayModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "protein_activity_assays"

    protein_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    activity_measured: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    readout: Mapped[str | None] = mapped_column(String(128), nullable=True)
    throughput: Mapped[str | None] = mapped_column(String(64), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(128), nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)


class UnpublishedStructureModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "unpublished_structures"

    protein_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    resolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    ligands: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_experimental: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
