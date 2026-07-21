"""Cross-entity tag-browse read model — the DTO and reader protocol.

Pure read path: given a set of tags, list every entity (across all six
taggable types) that carries them, each with a display label. The row DTO and
reader protocol live here (CQRS reader, mirrors chem-cellar's
``application.workspace_config.tagging.list_tag_entities``); the concrete
SQLAlchemy implementation is in
``infrastructure.persistence.sqlalchemy.tagging.tag_browse_repository``.

This file holds the DTO + protocol, plus the query object and its handler
(``ListTagEntitiesQuery`` / ``ListTagEntities``), which call through to the
infra reader above via the ``TagBrowseReader`` protocol.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_same_workspace, require_workspace_role
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError


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


@dataclass(frozen=True, kw_only=True)
class ListTagEntitiesQuery(Query):
    workspace_id: uuid.UUID
    tag_ids: list[uuid.UUID]
    match_all: bool = False
    types: list[str] | None = None
    limit: int = 200


class ListTagEntities:
    def __init__(self, uow: UnitOfWork, repo: TagBrowseReader) -> None:
        self._uow = uow
        self._repo = repo

    async def __call__(
        self, input: ListTagEntitiesQuery, auth: AuthContext | None = None
    ) -> Result[list[TaggedEntityRow], DomainError]:
        require_workspace_role(auth, "viewer")
        require_same_workspace(auth, input.workspace_id)
        async with self._uow:
            rows = await self._repo.find_entities_for_tags(
                input.workspace_id,
                input.tag_ids,
                match_all=input.match_all,
                types=input.types,
                limit=input.limit,
            )
        return Success(rows)
