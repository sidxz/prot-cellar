"""Workspace config DI bindings — registers Organization use cases into Lagom."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.workspace_config.create_organization import CreateOrganization
from protcellar.application.workspace_config.get_organization import GetOrganization
from protcellar.application.workspace_config.list_organizations import ListOrganizations
from protcellar.application.workspace_config.update_organization import UpdateOrganization
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.workspace_config.organization_repository import (  # noqa: E501
    SQLAlchemyOrganizationRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_workspace_config(container: Container) -> None:
    """Register Organization use cases into the Lagom container."""

    # --- Organizations ---
    def _org_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyOrganizationRepository(uow), c[EventDispatcher])

        return _f

    def _org_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyOrganizationRepository(uow))

        return _f

    container.define(CreateOrganization, _org_cmd(CreateOrganization))
    container.define(UpdateOrganization, _org_cmd(UpdateOrganization))
    container.define(GetOrganization, _org_query(GetOrganization))
    container.define(ListOrganizations, _org_query(ListOrganizations))
