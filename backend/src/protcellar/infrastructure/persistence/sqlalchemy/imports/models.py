from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from protcellar.infrastructure.persistence.sqlalchemy.base import (
    Base,
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


class ImportRunModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "import_runs"

    import_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    upload_ref: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportUploadModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    __tablename__ = "import_uploads"

    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
