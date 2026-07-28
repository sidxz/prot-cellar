"""Application-layer pagination primitives."""

from __future__ import annotations

import uuid
from datetime import datetime

from protcellar.domain.shared.pagination import PageResult

# Re-export domain types so application-layer imports work.
__all__ = [
    "BULK_PAGE_SIZE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PageResult",
    "clamp_limit",
    "encode_ts_cursor",
    "parse_cursor",
    "parse_ts_cursor",
]

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
# Bulk catalog reads (reporting/data-views pulls a whole proteome's genes/proteins at once) opt in
# via clamp_limit(..., max_size=BULK_PAGE_SIZE), so ~4k rows come back in one keyset page instead of
# ~20 round-trips. Ceiling, not comfort: the UoW's track() is O(n²) in page size and responses are
# buffered (not streamed), so keep this a few thousand — larger proteomes still page via the cursor.
BULK_PAGE_SIZE = 5000


def parse_cursor(cursor: str | None) -> uuid.UUID | None:
    """Parse a cursor string into a UUID, or return ``None``."""
    if cursor is None:
        return None
    try:
        return uuid.UUID(cursor)
    except ValueError:
        return None


def encode_ts_cursor(ts: datetime, id_: uuid.UUID) -> str:
    """Opaque keyset cursor for ``ORDER BY <ts> DESC, id DESC`` listings."""
    return f"{ts.isoformat()}|{id_}"


def parse_ts_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    """Parse a cursor produced by ``encode_ts_cursor``."""
    if not cursor:
        return None
    try:
        ts_str, id_str = cursor.split("|", 1)
        return datetime.fromisoformat(ts_str), uuid.UUID(id_str)
    except (ValueError, AttributeError):
        return None


def clamp_limit(limit: int | None, *, max_size: int = MAX_PAGE_SIZE) -> int:
    """Clamp a requested page size to [1, max_size], defaulting to DEFAULT_PAGE_SIZE."""
    if limit is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(limit, max_size))
