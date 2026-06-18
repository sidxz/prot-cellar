"""Provenance mixin for imported reference data (spec §7 baseline)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class ProvenanceMixin:
    source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_record_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
