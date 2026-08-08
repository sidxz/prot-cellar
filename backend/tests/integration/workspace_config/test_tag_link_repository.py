"""Integration tests for SQLAlchemyTagLinkRepository — the tag-link repos are
the ONE deliberate semantic change from chem-cellar: entity visibility is
"global-or-mine" (an entity pinned to SHARED_WORKSPACE_ID is taggable from
every workspace) rather than chem-cellar's strict "entity.workspace_id ==
workspace_id". These tests prove both directions of that rule, plus the
organism tombstone override, plus the add/remove/set round trip.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.workspace_config.tagging.tag import TaggableEntityType, TagName
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import TargetTagLinkModel
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_link_repository import (
    SQLAlchemyTagLinkRepositoryProvider,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository import (
    SQLAlchemyTagRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import OrganismModel
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# The testcontainer engine/session_factory fixtures are session-scoped, so their
# asyncpg pool binds to one event loop; run these tests on a shared session loop
# (the default function-scoped loop would close between tests -> "Event loop is closed").
pytestmark = pytest.mark.asyncio(loop_scope="session")


def _organism(**overrides: object) -> OrganismModel:
    defaults = dict(
        workspace_id=SHARED_WORKSPACE_ID,
        rank="species",
        scientific_name=f"Testus organismus {uuid.uuid4()}",
        source="test",
    )
    defaults.update(overrides)
    return OrganismModel(**defaults)  # type: ignore[arg-type]


def _target(**overrides: object) -> TargetModel:
    defaults = dict(
        workspace_id=uuid.uuid4(),
        pref_name="RpoB",
        target_type="PROTEIN",
    )
    defaults.update(overrides)
    return TargetModel(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The core adaptation: global-or-mine visibility
# ---------------------------------------------------------------------------


async def test_global_entity_is_taggable_from_any_workspace(uow: AsyncUnitOfWork) -> None:
    """An organism pinned to SHARED_WORKSPACE_ID (shared reference data, e.g.
    imported from NCBI) must be a valid tag target from ANY workspace, not
    just GLOBAL itself — this is the semantic change from chem-cellar."""
    organism = _organism()
    async with uow:
        uow.session.add(organism)
        await uow.commit()

    some_workspace = uuid.uuid4()  # a real, non-global workspace
    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        assert await repo.entity_exists_in_workspace(some_workspace, organism.id) is True


async def test_target_is_only_visible_to_its_own_workspace(uow: AsyncUnitOfWork) -> None:
    """Target is per-workspace data (not global reference data) — it must NOT
    leak across workspaces the way global entities do."""
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    target = _target(workspace_id=ws_a)
    async with uow:
        uow.session.add(target)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        assert await repo.entity_exists_in_workspace(ws_a, target.id) is True
        assert await repo.entity_exists_in_workspace(ws_b, target.id) is False


async def test_unknown_entity_id_is_not_visible(uow: AsyncUnitOfWork) -> None:
    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        assert await repo.entity_exists_in_workspace(uuid.uuid4(), uuid.uuid4()) is False


# ---------------------------------------------------------------------------
# Organism tombstone override — merged/deleted organisms are not valid targets
# ---------------------------------------------------------------------------


async def test_merged_organism_is_not_a_valid_tag_target(uow: AsyncUnitOfWork) -> None:
    survivor = _organism()
    async with uow:
        uow.session.add(survivor)
        await uow.commit()

    merged = _organism(merged_into_id=survivor.id)
    async with uow:
        uow.session.add(merged)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        # The un-merged survivor is still a valid target...
        assert await repo.entity_exists_in_workspace(uuid.uuid4(), survivor.id) is True
        # ...but the tombstoned row is not, even though it's GLOBAL and matches
        # every other visibility criterion.
        assert await repo.entity_exists_in_workspace(uuid.uuid4(), merged.id) is False


async def test_soft_deleted_organism_is_not_a_valid_tag_target(uow: AsyncUnitOfWork) -> None:
    organism = _organism(is_deleted=True)
    async with uow:
        uow.session.add(organism)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        assert await repo.entity_exists_in_workspace(uuid.uuid4(), organism.id) is False


# ---------------------------------------------------------------------------
# add / remove / set round trip
# ---------------------------------------------------------------------------


async def test_add_remove_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    target = _target(workspace_id=ws)
    async with uow:
        uow.session.add(target)
        tag = await SQLAlchemyTagRepository(uow).get_or_create(ws, TagName(key="priority"), user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        inserted = await repo.add(ws, target.id, tag.id, user)
        await uow.commit()
    assert inserted is True

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        duplicate_inserted = await repo.add(ws, target.id, tag.id, user)
        await uow.commit()
    assert duplicate_inserted is False

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        tags = await repo.find_tags_for_entity(ws, target.id)
    assert [t.id for t in tags] == [tag.id]

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        await repo.remove(ws, target.id, tag.id)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        tags_after_remove = await repo.find_tags_for_entity(ws, target.id)
    assert tags_after_remove == []


async def test_set_for_entity_does_not_delete_other_workspaces_tags(uow: AsyncUnitOfWork) -> None:
    """Regression test: set_for_entity's reconcile-DELETE must be scoped to the
    caller's own tags. Reference entities (organisms, proteins, ...) are
    GLOBAL-pinned and tagged by MANY workspaces against the SAME row — an
    unscoped DELETE issued by workspace A's set_for_entity call collaterally
    deletes workspace B's tag links on that shared row. Cross-tenant data
    loss (the merge-blocking Critical from the whole-branch review)."""
    organism = _organism()
    ws_a, ws_b, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with uow:
        uow.session.add(organism)
        tag_repo = SQLAlchemyTagRepository(uow)
        tag_keep_a = await tag_repo.get_or_create(ws_a, TagName(key="keep-a"), user)
        tag_keep_b = await tag_repo.get_or_create(ws_b, TagName(key="keep-b"), user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        await repo.add(ws_a, organism.id, tag_keep_a.id, user)
        await repo.add(ws_b, organism.id, tag_keep_b.id, user)
        await uow.commit()

    # Workspace A reconciles its own tag set on the shared organism.
    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        await repo.set_for_entity(ws_a, organism.id, [tag_keep_a.id], user)
        await uow.commit()

    # Workspace B's tag link on the SAME shared row must survive untouched.
    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        tags_b = await repo.find_tags_for_entity(ws_b, organism.id)
        tags_a = await repo.find_tags_for_entity(ws_a, organism.id)
    assert {t.id for t in tags_b} == {tag_keep_b.id}
    assert {t.id for t in tags_a} == {tag_keep_a.id}


async def test_add_rejects_entity_outside_workspace(uow: AsyncUnitOfWork) -> None:
    """add() must consult entity_exists_in_workspace — a Target from another
    workspace is not taggable, and no link row should be inserted."""
    ws_a, ws_b, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    target = _target(workspace_id=ws_a)
    async with uow:
        uow.session.add(target)
        tag = await SQLAlchemyTagRepository(uow).get_or_create(ws_b, TagName(key="env"), user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        inserted = await repo.add(ws_b, target.id, tag.id, user)
        await uow.commit()
    assert inserted is False

    async with uow:
        result = await uow.session.execute(
            select(TargetTagLinkModel).where(TargetTagLinkModel.target_id == target.id)
        )
        assert result.scalar_one_or_none() is None


async def test_set_for_entity_replaces_tag_set(uow: AsyncUnitOfWork) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    target = _target(workspace_id=ws)
    async with uow:
        uow.session.add(target)
        tag_repo = SQLAlchemyTagRepository(uow)
        tag_a = await tag_repo.get_or_create(ws, TagName(key="a"), user)
        tag_b = await tag_repo.get_or_create(ws, TagName(key="b"), user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        await repo.set_for_entity(ws, target.id, [tag_a.id, tag_b.id], user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        tags = await repo.find_tags_for_entity(ws, target.id)
        assert {t.id for t in tags} == {tag_a.id, tag_b.id}

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        await repo.set_for_entity(ws, target.id, [tag_b.id], user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        tags = await repo.find_tags_for_entity(ws, target.id)
        assert {t.id for t in tags} == {tag_b.id}
