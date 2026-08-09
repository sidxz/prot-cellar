"""SQLAlchemy models for workspace configuration context."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class OrganizationModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    """Organization — provenance entity for companies, partners, CROs, vendors."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_org_ws_name"),)


class ExtensionFieldDefModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    """A workspace's declaration of one extra field on one target-biology record kind.

    `name` is the key inside that kind's `extensions` JSONB bag. It is immutable in the
    domain: renaming it would orphan every stored value.
    """

    __tablename__ = "extension_field_defs"
    __table_args__ = (
        Index(
            "uq_extension_field_defs_ws_kind_name",
            "workspace_id",
            "kind",
            "name",
            unique=True,
        ),
        Index("ix_extension_field_defs_ws_kind", "workspace_id", "kind"),
    )

    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    show_in_table: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
