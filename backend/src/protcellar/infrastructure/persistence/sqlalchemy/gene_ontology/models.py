"""SQLAlchemy models for the gene_ontology context."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import Base, EntityModelMixin


class GoTermModel(Base, EntityModelMixin):
    __tablename__ = "go_terms"
    __table_args__ = (Index("ix_go_terms_go_id", "go_id", unique=True),)

    go_id: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    replaced_by: Mapped[str | None] = mapped_column(String(12), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="go", nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GoEdgeModel(Base, EntityModelMixin):
    __tablename__ = "go_edges"
    __table_args__ = (Index("ix_go_edges_parent_child", "parent_go_id", "child_go_id"),)

    child_go_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    parent_go_id: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(16), nullable=False)
