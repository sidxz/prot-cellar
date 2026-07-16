from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from protcellar.application.target_biology._import_support import ItemResult


class Sink(Protocol):
    """The single seam a plugin writes through. In-tree today; an HTTP client later.

    Records are the per-record import DTOs (e.g. EssentialityImportRecord). The sink
    implementation resolves record_type -> the matching BulkUpsert<X> command and
    stamps generation_method + source_run_id (the plugin never sees those)."""

    async def upsert(self, record_type: str, records: Sequence[object]) -> list[ItemResult]: ...
