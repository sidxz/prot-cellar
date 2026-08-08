"""Import repository protocols."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol, runtime_checkable

from protcellar.domain.imports.enums import ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.imports.upload import ImportUpload


@runtime_checkable
class ImportRunRepository(Protocol):
    async def save(self, run: ImportRun) -> None: ...

    async def get(self, workspace_id: uuid.UUID, id: uuid.UUID) -> ImportRun | None: ...

    async def get_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> ImportRun | None: ...

    async def list(
        self,
        *,
        workspace_id: uuid.UUID,
        cursor: tuple[datetime, uuid.UUID] | None = None,
        limit: int = 50,
    ) -> list[ImportRun]: ...

    async def find_active(self, import_type: ImportType, target_key: str) -> ImportRun | None: ...


@runtime_checkable
class ImportUploadRepository(Protocol):
    async def save(self, upload: ImportUpload) -> None: ...

    async def get(self, workspace_id: uuid.UUID, id: uuid.UUID) -> ImportUpload | None: ...
