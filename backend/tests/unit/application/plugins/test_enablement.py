"""Unit tests for plugin-enablement use cases (in-memory fake repo)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.plugins.enablement import (
    ListEnabledPluginIds,
    SetPluginEnablement,
    SetPluginEnablementCommand,
)
from protcellar.domain.shared.errors import AuthorizationError
from tests.fakes.fake_auth import FakeAuth


class _FakeRepo:
    def __init__(self) -> None:
        self.data: dict[uuid.UUID, set[str]] = {}

    async def enabled_ids(self, workspace_id: uuid.UUID) -> set[str]:
        return set(self.data.get(workspace_id, set()))

    async def enable(self, workspace_id: uuid.UUID, plugin_id: str, enabled_by) -> None:
        self.data.setdefault(workspace_id, set()).add(plugin_id)

    async def disable(self, workspace_id: uuid.UUID, plugin_id: str) -> None:
        self.data.get(workspace_id, set()).discard(plugin_id)


class _FakeUoW:
    async def commit(self) -> list:
        return []

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _admin(ws: uuid.UUID) -> FakeAuth:
    return FakeAuth(role="admin", workspace_id=ws, user_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_enable_then_disable_roundtrip() -> None:
    ws = uuid.uuid4()
    repo = _FakeRepo()
    setter = SetPluginEnablement(_FakeUoW(), repo)
    lister = ListEnabledPluginIds(_FakeUoW(), repo)

    pid = "dejesus_essentiality"
    await setter(SetPluginEnablementCommand(plugin_id=pid, enabled=True), _admin(ws))
    assert await lister(_admin(ws)) == {pid}

    await setter(SetPluginEnablementCommand(plugin_id=pid, enabled=False), _admin(ws))
    assert await lister(_admin(ws)) == set()


@pytest.mark.asyncio
async def test_enablement_is_workspace_scoped() -> None:
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    repo = _FakeRepo()
    setter = SetPluginEnablement(_FakeUoW(), repo)
    lister = ListEnabledPluginIds(_FakeUoW(), repo)

    await setter(SetPluginEnablementCommand(plugin_id="p1", enabled=True), _admin(ws_a))
    assert await lister(_admin(ws_a)) == {"p1"}
    assert await lister(_admin(ws_b)) == set()  # other workspace unaffected


@pytest.mark.asyncio
async def test_set_enablement_requires_admin() -> None:
    setter = SetPluginEnablement(_FakeUoW(), _FakeRepo())
    editor = FakeAuth(role="editor", workspace_id=uuid.uuid4(), user_id=uuid.uuid4())
    with pytest.raises(AuthorizationError):
        await setter(SetPluginEnablementCommand(plugin_id="p1", enabled=True), editor)
