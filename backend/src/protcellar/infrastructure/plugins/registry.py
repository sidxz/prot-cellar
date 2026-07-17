from __future__ import annotations

import importlib
import logging
from typing import cast

from protcellar.application.plugins.manifest import PluginManifest
from protcellar.application.plugins.protocol import IngestionPlugin

logger = logging.getLogger(__name__)

# Config-driven discovery. Each path is a package exposing `manifest.MANIFEST`
# (runtime-light — safe to import just to list the catalog) and `plugin.PLUGIN`
# (the instance, which may pull heavy runtime deps, e.g. an AI SDK). Listing
# imports only the manifest; running imports the plugin for the one being run.
ENABLED_PLUGINS: tuple[str, ...] = ("protcellar.infrastructure.plugins.dejesus_essentiality",)


def _load_manifest(path: str) -> PluginManifest | None:
    try:
        return cast("PluginManifest", importlib.import_module(f"{path}.manifest").MANIFEST)
    except Exception:  # one broken plugin must not sink the whole catalog
        logger.exception("plugin package %s: manifest failed to import", path)
        return None


def all_manifests() -> list[PluginManifest]:
    """List catalog manifests without importing any plugin's run-time deps."""
    return [m for path in ENABLED_PLUGINS if (m := _load_manifest(path)) is not None]


def get_plugin(plugin_id: str) -> IngestionPlugin:
    """Import only the requested plugin's run-time module (`plugin.PLUGIN`)."""
    for path in ENABLED_PLUGINS:
        manifest = _load_manifest(path)
        if manifest is not None and manifest.id == plugin_id:
            return cast("IngestionPlugin", importlib.import_module(f"{path}.plugin").PLUGIN)
    raise KeyError(f"unknown plugin '{plugin_id}'")
