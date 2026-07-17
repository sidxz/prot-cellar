from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from protcellar.application.auth import AuthContext
from protcellar.application.imports.progress_reporter import ProgressReporter
from protcellar.application.plugins.sink import Sink


@dataclass(frozen=True, kw_only=True)
class PluginRunContext:
    """Everything a plugin needs at run time — mirrors ImportRuntime, minus wiring."""

    params: dict[str, Any]
    organism_id: uuid.UUID | None
    load_upload: Callable[[uuid.UUID], Awaitable[bytes]]
    sink: Sink
    reporter: ProgressReporter
    auth: AuthContext
    # Env-sourced by the dispatch adapter from manifest.requires_secrets — never
    # from params (params persist plaintext on the ImportRun). Empty until a plugin
    # declares requires_secrets; this is the seam an AI plugin reads its key from.
    secrets: dict[str, str] = field(default_factory=dict)
