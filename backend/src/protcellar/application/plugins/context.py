from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
