"""Integration tests for SQLAlchemyTagLinkRepository — the tag-link repos are
the ONE deliberate semantic change from chem-cellar: entity visibility is
"global-or-mine" (an entity pinned to GLOBAL_WORKSPACE_ID is taggable from
every workspace) rather than chem-cellar's strict "entity.workspace_id ==
workspace_id". These tests prove both directions of that rule, plus the
organism tombstone override, plus the add/remove/set round trip.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
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
        workspace_id=GLOBAL_WORKSPACE_ID,
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
    """An organism pinned to GLOBAL_WORKSPACE_ID (shared reference data, e.g.
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
