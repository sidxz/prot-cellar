from __future__ import annotations

import uuid
from datetime import datetime

from protcellar.domain.shared.entity import AggregateRoot


class ImportUpload(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        filename: str,
        content_type: str | None,
        data: bytes,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = workspace_id
        self.filename = filename
        self.content_type = content_type
        self.data = data

    @classmethod
    def create(
        cls, *, workspace_id: uuid.UUID, filename: str, content_type: str | None, data: bytes
    ) -> ImportUpload:
        return cls(
            workspace_id=workspace_id, filename=filename, content_type=content_type, data=data
        )
