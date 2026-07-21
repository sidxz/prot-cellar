"""Integration tests for SQLAlchemyTagBrowseRepository — the cross-entity tag
browse read model. Proves the UNION ALL spans multiple taggable types with the
correct per-type label column, that a GLOBAL-pinned entity is included (the
global-or-mine visibility rule, same as tag_link_repository.py), and that
match_all narrows to entities carrying every queried tag.
"""

from __future__ import annotations

import uuid

import pytest

from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.workspace_config.tagging.tag import TaggableEntityType, TagName
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_browse_repository import (
    SQLAlchemyTagBrowseRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_link_repository import (
    SQLAlchemyTagLinkRepositoryProvider,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository import (
    SQLAlchemyTagRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import OrganismModel
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# Session-scoped loop: the testcontainer engine/session_factory fixtures are
# session-scoped, so their asyncpg pool binds to one event loop (see
# test_tag_link_repository.py for the same rationale).
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


async def test_browse_spans_entity_types_and_includes_global_entity(
    uow: AsyncUnitOfWork,
) -> None:
    """A GLOBAL-pinned Organism and a workspace-scoped Target, tagged with the
    SAME tag, must both appear in one workspace's browse results — proving both
    the multi-type UNION and that global entities are not silently dropped."""
    ws, user = uuid.uuid4(), uuid.uuid4()
    organism = _organism()
    target = _target(workspace_id=ws)

    async with uow:
        uow.session.add_all([organism, target])
        tag = await SQLAlchemyTagRepository(uow).get_or_create(
            ws, TagName(key="priority", value="high"), user
        )
        await uow.commit()

    async with uow:
        provider = SQLAlchemyTagLinkRepositoryProvider(uow)
        await provider.for_type(TaggableEntityType.ORGANISM).add(ws, organism.id, tag.id, user)
        await provider.for_type(TaggableEntityType.TARGET).add(ws, target.id, tag.id, user)
        await uow.commit()

    async with uow:
        browse = SQLAlchemyTagBrowseRepository(uow)
        rows = await browse.find_entities_for_tags(ws, [tag.id])

    by_type = {r.entity_type: r for r in rows}
    assert set(by_type) == {"Organism", "Target"}
    assert by_type["Organism"].entity_id == organism.id
    assert by_type["Organism"].label == organism.scientific_name
    assert by_type["Target"].entity_id == target.id
    assert by_type["Target"].label == target.pref_name


async def test_browse_match_all_narrows_to_entities_carrying_every_tag(
    uow: AsyncUnitOfWork,
) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    both = _target(workspace_id=ws, pref_name="Both")
    red_only = _target(workspace_id=ws, pref_name="RedOnly")

    async with uow:
        uow.session.add_all([both, red_only])
        tag_repo = SQLAlchemyTagRepository(uow)
        red = await tag_repo.get_or_create(ws, TagName(key="color", value="red"), user)
        blue = await tag_repo.get_or_create(ws, TagName(key="color", value="blue"), user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        await repo.add(ws, both.id, red.id, user)
        await repo.add(ws, both.id, blue.id, user)
        await repo.add(ws, red_only.id, red.id, user)
        await uow.commit()

    async with uow:
        browse = SQLAlchemyTagBrowseRepository(uow)
        any_rows = await browse.find_entities_for_tags(ws, [red.id, blue.id], match_all=False)
        all_rows = await browse.find_entities_for_tags(ws, [red.id, blue.id], match_all=True)

    assert {r.entity_id for r in any_rows} == {both.id, red_only.id}
    assert {r.entity_id for r in all_rows} == {both.id}


async def test_browse_does_not_surface_a_foreign_workspaces_tag(uow: AsyncUnitOfWork) -> None:
    """A tag_id belonging to another workspace must yield no rows, even if it
    happens to be linked to a global entity — tags are workspace-scoped."""
    ws_a, ws_b, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    organism = _organism()

    async with uow:
        uow.session.add(organism)
        tag = await SQLAlchemyTagRepository(uow).get_or_create(
            ws_a, TagName(key="scope"), user
        )
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.ORGANISM)
        await repo.add(ws_a, organism.id, tag.id, user)
        await uow.commit()

    async with uow:
        browse = SQLAlchemyTagBrowseRepository(uow)
        rows = await browse.find_entities_for_tags(ws_b, [tag.id])

    assert rows == []
