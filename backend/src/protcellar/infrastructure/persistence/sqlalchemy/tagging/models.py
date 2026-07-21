"""SQLAlchemy models for tags + per-entity link tables.

The unique index on (workspace_id, normalized_key, normalized_value) uses
``NULLS NOT DISTINCT`` (PG15+) so value-less tags dedup correctly. Trigram GIN
indexes back autocomplete. Each link table has real FKs with ON DELETE CASCADE.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class TagModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    """Tag registry — one row per distinct (key, optional value) per workspace."""

    __tablename__ = "tags"

    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str | None] = mapped_column(String(256))
    normalized_key: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(256))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    __table_args__ = (
        Index(
            "uq_tags_ws_norm",
            "workspace_id",
            "normalized_key",
            "normalized_value",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index(
            "ix_tags_norm_key_trgm",
            "normalized_key",
            postgresql_using="gin",
            postgresql_ops={"normalized_key": "gin_trgm_ops"},
        ),
        Index(
            "ix_tags_norm_value_trgm",
            "normalized_value",
            postgresql_using="gin",
            postgresql_ops={"normalized_value": "gin_trgm_ops"},
        ),
        Index("ix_tags_ws_created_by", "workspace_id", "created_by"),
    )


class TagLinkMixin:
    """Shared non-PK columns for every tag link table."""

    assigned_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProteinTagLinkModel(Base, TagLinkMixin):
    __tablename__ = "protein_tags"

    protein_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("proteins.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_protein_tags_tag_id", "tag_id"),)


class GeneTagLinkModel(Base, TagLinkMixin):
    __tablename__ = "gene_tags"

    gene_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("genes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_gene_tags_tag_id", "tag_id"),)


class TargetTagLinkModel(Base, TagLinkMixin):
    __tablename__ = "target_tags"

    target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("targets.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_target_tags_tag_id", "tag_id"),)


class OrganismTagLinkModel(Base, TagLinkMixin):
    __tablename__ = "organism_tags"

    organism_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisms.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_organism_tags_tag_id", "tag_id"),)


class StrainTagLinkModel(Base, TagLinkMixin):
    __tablename__ = "strain_tags"

    strain_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("strains.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_strain_tags_tag_id", "tag_id"),)


class ProteomeTagLinkModel(Base, TagLinkMixin):
    __tablename__ = "proteome_tags"

    proteome_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("proteomes.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (Index("ix_proteome_tags_tag_id", "tag_id"),)
