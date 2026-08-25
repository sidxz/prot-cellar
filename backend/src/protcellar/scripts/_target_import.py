"""Shared plumbing for the one-off target loaders (PARSNIP, DAIKON).

Both read a curated external target list and create Targets in one workspace.
They differ only in the file shape and in how components are resolved.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Import the full model registry: TargetModel's organism_id FK cannot be mapped
# unless OrganismModel is registered too, and a script imports far less than the app.
import protcellar.infrastructure.persistence.sqlalchemy.metadata  # noqa: F401
from protcellar.application.target.create_target import CreateTarget, CreateTargetCommand
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.sqlalchemy.target.target_repository import (
    SQLAlchemyTargetRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


class WorkspaceAuth:
    """Admin auth pinned to the workspace being seeded."""

    workspace_role = "admin"
    is_admin = True

    def __init__(self, workspace_id: uuid.UUID) -> None:
        self.workspace_id = workspace_id
        self.user_id = workspace_id

    def has_role(self, minimum_role: str) -> bool:
        return True


class NoopDispatcher:
    async def dispatch_all(self, events: object) -> None:
        return None


async def sole_workspace_with_targets(uow: AsyncUnitOfWork) -> uuid.UUID:
    rows = (await uow.session.execute(select(TargetModel.workspace_id).distinct())).scalars().all()
    if len(rows) != 1:
        raise SystemExit(
            f"--workspace-id is required (found {len(rows)} workspaces owning targets)."
        )
    return rows[0]


async def create_target(
    factory: async_sessionmaker[AsyncSession],
    command: CreateTargetCommand,
    auth: WorkspaceAuth,
) -> None:
    """Run CreateTarget in its own transaction."""
    uow = AsyncUnitOfWork(factory)
    use_case = CreateTarget(
        uow,
        SQLAlchemyTargetRepository(uow),
        SQLAlchemyProteinRepository(uow),
        SQLAlchemyGeneRepository(uow),
        NoopDispatcher(),
    )
    (await use_case(command, auth=auth)).unwrap()
