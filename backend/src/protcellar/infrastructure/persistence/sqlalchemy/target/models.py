"""SQLAlchemy models for the Target context."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class TargetModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "targets"

    pref_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organism_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisms.id"), nullable=True, index=True
    )
    chembl_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    pharmacological_class: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)

    components: Mapped[list[TargetComponentModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TargetComponentModel.position",
        foreign_keys="TargetComponentModel.target_id",
    )


class TargetComponentModel(Base, EntityModelMixin):
    __tablename__ = "target_components"

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targets.id"), nullable=False, index=True
    )
    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
