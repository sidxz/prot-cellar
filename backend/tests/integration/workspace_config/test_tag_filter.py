"""Integration test for tag_filter_subquery — any-logic vs all-logic tag
filtering against a real link table (TargetTagLinkModel)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from protcellar.domain.workspace_config.tagging.tag import TaggableEntityType, TagName
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import TargetTagLinkModel
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_filter import (
    tag_filter_subquery,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_link_repository import (
    SQLAlchemyTagLinkRepositoryProvider,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository import (
    SQLAlchemyTagRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_tag_filter_subquery_any_vs_all(uow: AsyncUnitOfWork) -> None:
    ws, user = uuid.uuid4(), uuid.uuid4()
    t_both = TargetModel(workspace_id=ws, pref_name="Both", target_type="PROTEIN")
    t_red_only = TargetModel(workspace_id=ws, pref_name="RedOnly", target_type="PROTEIN")
    t_blue_only = TargetModel(workspace_id=ws, pref_name="BlueOnly", target_type="PROTEIN")
    t_neither = TargetModel(workspace_id=ws, pref_name="Neither", target_type="PROTEIN")

    async with uow:
        uow.session.add_all([t_both, t_red_only, t_blue_only, t_neither])
        tag_repo = SQLAlchemyTagRepository(uow)
        red = await tag_repo.get_or_create(ws, TagName(key="color", value="red"), user)
        blue = await tag_repo.get_or_create(ws, TagName(key="color", value="blue"), user)
        await uow.commit()

    async with uow:
        repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
        await repo.add(ws, t_both.id, red.id, user)
        await repo.add(ws, t_both.id, blue.id, user)
        await repo.add(ws, t_red_only.id, red.id, user)
        await repo.add(ws, t_blue_only.id, blue.id, user)
        await uow.commit()

    async with uow:
        any_subq = tag_filter_subquery(
            TargetTagLinkModel, "target_id", [red.id, blue.id], workspace_id=ws, match_all=False
        )
        any_result = await uow.session.execute(select(any_subq.subquery()))
        any_ids = {row[0] for row in any_result.all()}

        all_subq = tag_filter_subquery(
            TargetTagLinkModel, "target_id", [red.id, blue.id], workspace_id=ws, match_all=True
        )
        all_result = await uow.session.execute(select(all_subq.subquery()))
        all_ids = {row[0] for row in all_result.all()}

    assert any_ids == {t_both.id, t_red_only.id, t_blue_only.id}
    assert all_ids == {t_both.id}
    assert t_neither.id not in any_ids
