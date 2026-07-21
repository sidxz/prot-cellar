"""Unit tests for SetEntityTags (in-memory fakes — no DB).

Mandatory behavior: reconciling an entity's tag set from {A, B} to {B, C}
must ADD C, REMOVE A, and KEEP B — and must not emit a spurious
TagAssigned/TagUnassigned for the unchanged tag B.
"""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.workspace_config.tagging.set_entity_tags import (
    SetEntityTags,
    SetEntityTagsCommand,
    TagInput,
)
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.events import DomainEvent
from protcellar.domain.workspace_config.tagging.events import TagAssigned, TagUnassigned
from protcellar.domain.workspace_config.tagging.tag import Tag, TaggableEntityType, TagName
from tests.fakes.fake_auth import FakeAuth


class _FakeTagRepo:
    """Registry keyed by normalized (key, value); shares tag objects via ``registry``."""

    def __init__(self, registry: dict[uuid.UUID, Tag]) -> None:
        self._registry = registry
        self._by_norm: dict[tuple[str, str | None], Tag] = {}

    async def get_or_create(
        self, workspace_id: uuid.UUID, name: TagName, created_by: uuid.UUID
    ) -> Tag:
        key = (name.normalized_key, name.normalized_value)
        existing = self._by_norm.get(key)
        if existing is not None:
            return existing
        tag = Tag.create(
            workspace_id=workspace_id, key=name.key, value=name.value, created_by=created_by
        )
        self._by_norm[key] = tag
        self._registry[tag.id] = tag
        return tag


class _FakeTagLinkRepo:
    """Bound to one entity type; ``links`` maps entity_id -> list of tag_ids."""

    def __init__(self, registry: dict[uuid.UUID, Tag]) -> None:
        self._registry = registry
        self.links: dict[uuid.UUID, list[uuid.UUID]] = {}

    async def entity_exists_in_workspace(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID
    ) -> bool:
        return True

    async def find_tags_for_entity(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID
    ) -> list[Tag]:
        return [self._registry[tid] for tid in self.links.get(entity_id, [])]

    async def set_for_entity(
        self,
        workspace_id: uuid.UUID,
        entity_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        assigned_by: uuid.UUID,
    ) -> None:
        self.links[entity_id] = list(tag_ids)


class _FakeTagLinkProvider:
    def __init__(self, repo: _FakeTagLinkRepo) -> None:
        self._repo = repo

    def for_type(self, entity_type: TaggableEntityType) -> _FakeTagLinkRepo:
        return self._repo


class _FakeUoW:
    def __init__(self) -> None:
        self._tracked: list[AggregateRoot] = []

    @property
    def is_active(self) -> bool:
        return True

    def track(self, aggregate: AggregateRoot) -> None:
        if aggregate not in self._tracked:
            self._tracked.append(aggregate)

    async def commit(self) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        for aggregate in self._tracked:
            events.extend(aggregate.collect_events())
            aggregate.clear_events()
        return events

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _CapturingDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[DomainEvent] = []

    async def dispatch_all(self, events: list[DomainEvent]) -> None:
        self.dispatched.extend(events)


@pytest.mark.asyncio
async def test_reconcile_adds_new_removes_missing_keeps_unchanged() -> None:
    registry: dict[uuid.UUID, Tag] = {}
    tag_repo = _FakeTagRepo(registry)
    link_repo = _FakeTagLinkRepo(registry)
    provider = _FakeTagLinkProvider(link_repo)
    uow = _FakeUoW()
    dispatcher = _CapturingDispatcher()
    handler = SetEntityTags(uow, tag_repo, provider, dispatcher)  # type: ignore[arg-type]

    auth = FakeAuth(role="editor")
    workspace_id = auth.workspace_id
    entity_id = uuid.uuid4()

    # Entity currently carries {A, B}.
    tag_a = await tag_repo.get_or_create(workspace_id, TagName(key="A"), auth.user_id)
    tag_b = await tag_repo.get_or_create(workspace_id, TagName(key="B"), auth.user_id)
    link_repo.links[entity_id] = [tag_a.id, tag_b.id]

    command = SetEntityTagsCommand(
        workspace_id=workspace_id,
        entity_type=TaggableEntityType.PROTEIN,
        entity_id=entity_id,
        tags=(TagInput(key="B"), TagInput(key="C")),
        assigned_by=auth.user_id,
    )

    result = await handler(command, auth=auth)
    tags = result.unwrap()

    # Resulting set is {B, C} — C added, A removed, B kept.
    assert {t.key for t in tags} == {"B", "C"}
    tag_c = next(t for t in tags if t.key == "C")
    assert set(link_repo.links[entity_id]) == {tag_b.id, tag_c.id}

    # Exactly one TagAssigned (for C) and one TagUnassigned (for A) — the
    # unchanged tag B must not appear in either, i.e. no spurious event.
    assigned = [e for e in dispatcher.dispatched if isinstance(e, TagAssigned)]
    unassigned = [e for e in dispatcher.dispatched if isinstance(e, TagUnassigned)]
    assert [e.aggregate_id for e in assigned] == [tag_c.id]
    assert [e.aggregate_id for e in unassigned] == [tag_a.id]
