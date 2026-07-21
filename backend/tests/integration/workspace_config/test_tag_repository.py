"""Integration tests for SQLAlchemyTagRepository."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from protcellar.domain.workspace_config.tagging.tag import TagName
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import TagModel
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository import (
    SQLAlchemyTagRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# The testcontainer engine/session_factory fixtures are session-scoped, so their
# asyncpg pool binds to one event loop; run these tests on a shared session loop
# (the default function-scoped loop would close between tests -> "Event loop is closed").
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _tag_count(uow: AsyncUnitOfWork, workspace_id: uuid.UUID) -> int:
    result = await uow.session.execute(
        select(func.count()).select_from(TagModel).where(TagModel.workspace_id == workspace_id)
    )
    return result.scalar_one()


async def test_get_or_create_is_idempotent(uow: AsyncUnitOfWork) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    name = TagName(key="env", value="prod")

    async with uow:
        first = await SQLAlchemyTagRepository(uow).get_or_create(ws, name, user)
        await uow.commit()

    async with uow:
        second = await SQLAlchemyTagRepository(uow).get_or_create(ws, name, user)
        await uow.commit()

    assert first.id == second.id

    async with uow:
        assert await _tag_count(uow, ws) == 1


async def test_get_or_create_valueless_dedup(uow: AsyncUnitOfWork) -> None:
    """NULLS NOT DISTINCT on the unique index: two value-less get_or_create
    calls for the same key must collapse to one row, not two."""
    ws, user = uuid.uuid4(), uuid.uuid4()
    name = TagName(key="priority")

    async with uow:
        first = await SQLAlchemyTagRepository(uow).get_or_create(ws, name, user)
        await uow.commit()

    async with uow:
        second = await SQLAlchemyTagRepository(uow).get_or_create(ws, name, user)
        await uow.commit()

    assert first.id == second.id
    assert first.value is None

    async with uow:
        assert await _tag_count(uow, ws) == 1


async def test_find_by_normalized_round_trips(uow: AsyncUnitOfWork) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    name = TagName(key="Team", value="Bio")

    async with uow:
        created = await SQLAlchemyTagRepository(uow).get_or_create(ws, name, user)
        await uow.commit()

    async with uow:
        found = await SQLAlchemyTagRepository(uow).find_by_normalized(
            ws, TagName(key="team", value="bio")
        )

    assert found is not None
    assert found.id == created.id
    assert found.key == "Team"
    assert found.value == "Bio"
