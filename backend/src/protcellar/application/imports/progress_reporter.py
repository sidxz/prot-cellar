"""ProgressReporter protocol and no-op implementation.

This module contains only stdlib/typing imports — no infrastructure,
no domain, no third-party. It is safe to import from any layer.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting import progress to an external observer.

    All methods are coroutines so both sync-wrapped and async implementations
    can satisfy the protocol.
    """

    async def phase(self, label: str) -> None:
        """Signal that a named phase has begun."""
        ...

    async def advance(self, processed: int, total: int | None = None) -> None:
        """Report progress: *processed* items done out of *total* (if known)."""
        ...

    async def source_version(self, version: str | None) -> None:
        """Record the version string of the upstream data source."""
        ...


class NoopProgressReporter:
    """No-op implementation — safe as a default argument in runner constructors."""

    async def phase(self, label: str) -> None:
        return None

    async def advance(self, processed: int, total: int | None = None) -> None:
        return None

    async def source_version(self, version: str | None) -> None:
        return None
