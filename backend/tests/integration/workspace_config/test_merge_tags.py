"""Integration test for MergeTags — the one behavior that must be proven with
real repos: merging repoints an entity's links from source onto target (via
the real ``repoint`` SQL, across the ``for entity_type in TaggableEntityType``
loop) and deletes the source tag. A fake that no-ops ``repoint`` would prove
nothing, so this exercises the real SQLAlchemy tag + link repositories against
a testcontainer Postgres (mirrors ``test_tag_link_repository.py``).
"""

from __future__ import annotations

import uuid

import pytest
from returns.result import Success

from protcellar.application.workspace_config.tagging.merge_tags import (
    MergeTags,
    MergeTagsCommand,
)
from protcellar.domain.shared.events import DomainEvent
from protcellar.domain.workspace_config.tagging.events import TagMerged
from protcellar.domain.workspace_config.tagging.tag import TaggableEntityType, TagName
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_link_repository import (
    SQLAlchemyTagLinkRepositoryProvider,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository import (
    SQLAlchemyTagRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from tests.fakes.fake_auth import FakeAuth

# Same reasoning as test_tag_link_repository.py: the testcontainer engine's
# asyncpg pool is session-scoped, so these tests must share the session loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")


class _CapturingDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[DomainEvent] = []

    async def dispatch_all(self, events: list[DomainEvent]) -> None:
        self.dispatched.extend(events)


async def test_merge_repoints_entity_links_and_deletes_source(uow: AsyncUnitOfWork) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    entity = TargetModel(workspace_id=ws, pref_name="RpoB", target_type="PROTEIN")  # type: ignore[call-arg]

    tag_repo = SQLAlchemyTagRepository(uow)
    link_provider = SQLAlchemyTagLinkRepositoryProvider(uow)

    async with uow:
        uow.session.add(entity)
        source = await tag_repo.get_or_create(ws, TagName(key="src"), user)
        target = await tag_repo.get_or_create(ws, TagName(key="tgt"), user)
        await uow.commit()

    async with uow:
        link_repo = link_provider.for_type(TaggableEntityType.TARGET)
        inserted = await link_repo.add(ws, entity.id, source.id, user)
        await uow.commit()
    assert inserted is True

    dispatcher = _CapturingDispatcher()
    handler = MergeTags(uow, tag_repo, link_provider, dispatcher)
    auth = FakeAuth(role="admin", workspace_id=ws, user_id=user)
    cmd = MergeTagsCommand(workspace_id=ws, source_tag_id=source.id, target_tag_id=target.id)

    result = await handler(cmd, auth=auth)
    assert isinstance(result, Success)
    assert result.unwrap().id == target.id

    # The entity now carries target, not source — links were repointed, not duplicated.
    async with uow:
        link_repo = link_provider.for_type(TaggableEntityType.TARGET)
        entity_tags = await link_repo.find_tags_for_entity(ws, entity.id)
    assert [t.id for t in entity_tags] == [target.id]

    # Source tag itself is gone.
    async with uow:
        remaining = await tag_repo.find_owned(ws, source.id)
    assert remaining is None

    assert any(isinstance(e, TagMerged) for e in dispatcher.dispatched)
