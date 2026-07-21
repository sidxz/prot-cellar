"""Cross-entity tag-browse read model — the DTO and reader protocol.

Pure read path: given a set of tags, list every entity (across all six
taggable types) that carries them, each with a display label. The row DTO and
reader protocol live here (CQRS reader, mirrors chem-cellar's
``application.workspace_config.tagging.list_tag_entities``); the concrete
SQLAlchemy implementation is in
``infrastructure.persistence.sqlalchemy.tagging.tag_browse_repository``.

This file holds only the DTO + protocol for now — the query object and its
handler (``ListTagEntitiesQuery`` / ``ListTagEntities``) are added by a later
task that extends this same file, once the infra reader below exists for it
to call through.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, kw_only=True)
class TaggedEntityRow:
    """One entity (of any taggable type) that carries a queried tag."""

    entity_type: str
    entity_id: uuid.UUID
    label: str
    assigned_at: datetime


@runtime_checkable
class TagBrowseReader(Protocol):
    """Application-layer protocol for the cross-entity tag browse read-model."""

    async def find_entities_for_tags(
        self,
        workspace_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        *,
        match_all: bool = False,
        types: list[str] | None = None,
        limit: int = 200,
    ) -> list[TaggedEntityRow]: ...
