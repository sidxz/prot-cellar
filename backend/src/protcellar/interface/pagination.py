"""Cursor-based pagination utilities for API endpoints."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from protcellar.application.shared.pagination import (
    BULK_PAGE_SIZE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    clamp_limit,
    encode_ts_cursor,
    parse_cursor,
    parse_ts_cursor,
)

__all__ = [
    "BULK_PAGE_SIZE",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PaginatedResponse",
    "clamp_limit",
    "encode_ts_cursor",
    "parse_cursor",
    "parse_ts_cursor",
]

T = TypeVar("T")


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper.

    Attributes:
        items: The page of results.
        next_cursor: Opaque cursor for fetching the next page, or ``None``
            when there are no more results.
        total_count: Optional total count (only provided when feasible).
    """

    items: list[T]
    next_cursor: str | None = None
    total_count: int | None = None
