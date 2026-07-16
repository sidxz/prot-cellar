from __future__ import annotations

import importlib

from protcellar.application.plugins.manifest import PluginManifest
from protcellar.application.plugins.protocol import IngestionPlugin

# Config-driven discovery: each path is a package exporting a module-level `plugin`.
ENABLED_PLUGINS: tuple[str, ...] = ("protcellar.infrastructure.plugins.dejesus_essentiality",)

_REGISTRY: dict[str, IngestionPlugin] | None = None


def _registry() -> dict[str, IngestionPlugin]:
    # ponytail: module-level lazy cache — fine for a process-lifetime registry.
    global _REGISTRY
    if _REGISTRY is None:
        loaded: dict[str, IngestionPlugin] = {}
        for path in ENABLED_PLUGINS:
            plugin: IngestionPlugin = importlib.import_module(path).plugin
            loaded[plugin.manifest().id] = plugin
        _REGISTRY = loaded
    return _REGISTRY


def get_plugin(plugin_id: str) -> IngestionPlugin:
    try:
        return _registry()[plugin_id]
    except KeyError as e:
        raise KeyError(f"unknown plugin '{plugin_id}'") from e


def all_manifests() -> list[PluginManifest]:
    return [p.manifest() for p in _registry().values()]
