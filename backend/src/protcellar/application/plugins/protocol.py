from __future__ import annotations

from typing import Protocol

from protcellar.application.plugins.context import PluginRunContext
from protcellar.application.plugins.manifest import PluginManifest


class IngestionPlugin(Protocol):
    """Structural — a plugin matches this shape; no base class (docu-store style)."""

    @staticmethod
    def manifest() -> PluginManifest: ...

    async def run(self, ctx: PluginRunContext) -> None: ...
