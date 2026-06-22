from __future__ import annotations

import uuid
from datetime import datetime

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


class ImportUpload(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        filename: str,
        content_type: str | None,
        data: bytes,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.filename = filename
        self.content_type = content_type
        self.data = data

    @classmethod
    def create(cls, *, filename: str, content_type: str | None, data: bytes) -> ImportUpload:
        return cls(filename=filename, content_type=content_type, data=data)
