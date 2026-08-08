from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_import_run_round_trip_and_active_guard(
    database_url: str, _run_migrations: None
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    workspace_id = uuid.uuid4()
    try:
        async with AsyncUnitOfWork(factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            run = ImportRun.create(
                workspace_id=workspace_id,
                import_type=ImportType.PROTEOME,
                params={"proteome_id": "UP000001584", "force": False},
                target_key="UP000001584",
                requested_by=uuid.uuid4(),
            )
            await repo.save(run)
            await uow.commit()

        async with AsyncUnitOfWork(factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            loaded = await repo.get(workspace_id, run.id)
            assert loaded is not None
            assert loaded.import_type is ImportType.PROTEOME
            assert loaded.params["proteome_id"] == "UP000001584"
            assert loaded.status is ImportStatus.QUEUED
            active = await repo.find_active(ImportType.PROTEOME, "UP000001584")
            assert active is not None and active.id == run.id
            page = await repo.list(workspace_id=workspace_id, limit=10)
            assert any(r.id == run.id for r in page)
    finally:
        await engine.dispose()
