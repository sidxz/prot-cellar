"""SQLAlchemy models for the taxonomy context."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


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

    names: Mapped[list[OrganismNameModel]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", foreign_keys="OrganismNameModel.organism_id"
    )


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
