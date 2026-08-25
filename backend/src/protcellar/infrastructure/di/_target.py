"""Target DI bindings — registers Target use cases into Lagom."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.target.create_target import CreateTarget
from protcellar.application.target.get_target import GetTarget
from protcellar.application.target.list_targets import ListTargets
from protcellar.application.target.update_target import UpdateTarget
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.target_repository import (
    SQLAlchemyTargetRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_target(container: Container) -> None:
    """Register Target use cases into the Lagom container."""

    # --- Target (command — needs EventDispatcher) ---
    def _target_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyTargetRepository(uow), c[EventDispatcher])

        return _f

    # --- Target (query — no EventDispatcher) ---
    def _target_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyTargetRepository(uow))

        return _f

    # CreateTarget also reads proteins/genes to default a blank pref_name.
    def _create_target() -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return CreateTarget(
                uow,
                SQLAlchemyTargetRepository(uow),
                SQLAlchemyProteinRepository(uow),
                SQLAlchemyGeneRepository(uow),
                c[EventDispatcher],
            )

        return _f

    container.define(CreateTarget, _create_target())
    container.define(UpdateTarget, _target_cmd(UpdateTarget))
    container.define(GetTarget, _target_query(GetTarget))
    container.define(ListTargets, _target_query(ListTargets))
