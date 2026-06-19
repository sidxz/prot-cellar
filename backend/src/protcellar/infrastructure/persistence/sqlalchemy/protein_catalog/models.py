"""SQLAlchemy models for the Protein Catalog context."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

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
