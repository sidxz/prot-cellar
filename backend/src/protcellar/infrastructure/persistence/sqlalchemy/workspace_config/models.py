"""SQLAlchemy models for workspace configuration context."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    String,
    Text,
    UniqueConstraint,
)
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
