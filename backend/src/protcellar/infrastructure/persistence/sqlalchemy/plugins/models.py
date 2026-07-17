"""SQLAlchemy model for workspace-scoped plugin enablement."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import Base


class WorkspacePluginModel(Base):
    """One row == this plugin is enabled for this workspace (opt-in; absence = off).

    Natural composite key (workspace_id, plugin_id) — no surrogate id, since this
    is a workspace↔plugin association, not an aggregate with its own identity.
    """

    __tablename__ = "workspace_enabled_plugins"

    workspace_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    plugin_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    enabled_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
