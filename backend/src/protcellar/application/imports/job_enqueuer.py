"""JobEnqueuer protocol — application-layer abstraction over the job queue.

The concrete implementation (arq-backed) lives in infrastructure and is wired
up in Task 7.  Use cases depend only on this protocol.
"""

from __future__ import annotations

import uuid
from typing import Protocol


class JobEnqueuer(Protocol):
    """Enqueue an import job for background execution."""

    async def enqueue_import(self, import_run_id: uuid.UUID, workspace_id: uuid.UUID) -> None: ...
