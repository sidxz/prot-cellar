"""Ingestion-plugin enablement DI bindings."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.plugins.enablement import ListEnabledPluginIds, SetPluginEnablement
from protcellar.infrastructure.persistence.sqlalchemy.plugins.workspace_plugin_repository import (
    SQLAlchemyWorkspacePluginRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_plugins(container: Container) -> None:
    def _uc(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyWorkspacePluginRepository(uow))

        return _f

    container.define(ListEnabledPluginIds, _uc(ListEnabledPluginIds))
    container.define(SetPluginEnablement, _uc(SetPluginEnablement))
