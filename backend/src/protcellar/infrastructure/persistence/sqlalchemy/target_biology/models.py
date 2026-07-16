"""SQLAlchemy models for the target_biology context.

gene_id / target_gene_id are real FKs to genes.id (mirrors how target FKs to
proteins/organisms); the domain still references them as bare UUIDs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class EssentialityRecordModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "essentiality_records"

    gene_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("genes.id"), nullable=False, index=True
    )
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
    target_gene_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("genes.id"), nullable=False, index=True
    )
    provenance: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    extensions: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
