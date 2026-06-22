"""Integration tests for the arq import worker and DI smoke-checks."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.infrastructure.ingestion import worker as worker_mod
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

pytestmark = pytest.mark.asyncio


def _ctx(factory) -> dict:
    # No audit handler registered → dispatch_all is a harmless no-op.
    return {"session_factory": factory, "dispatcher": EventDispatcher()}


async def _seed_queued(factory) -> uuid.UUID:
    async with AsyncUnitOfWork(factory) as uow:
        repo = SQLAlchemyImportRunRepository(uow)
        run = ImportRun.create(
            import_type=ImportType.GO_ONTOLOGY,
            params={"force": False},
            target_key="go",
            requested_by=uuid.uuid4(),
        )
        await repo.save(run)
        await uow.commit()
        return run.id


async def test_worker_drives_queued_to_succeeded(
    database_url: str, _run_migrations: None, monkeypatch: object
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        run_id = await _seed_queued(factory)

        class _StubAdapter:
            import_type = ImportType.GO_ONTOLOGY

            async def run(self, rt):
                await rt.reporter.phase("upsert")
                return {"terms_upserted": 5, "edges": 9}

        monkeypatch.setitem(worker_mod.IMPORT_ADAPTERS, ImportType.GO_ONTOLOGY, _StubAdapter())
        await worker_mod.run_import(_ctx(factory), str(run_id))

        async with AsyncUnitOfWork(factory) as uow:
            run = await SQLAlchemyImportRunRepository(uow).get(run_id)
            assert run.status is ImportStatus.SUCCEEDED
            assert run.summary["terms_upserted"] == 5
    finally:
        await engine.dispose()


async def test_worker_marks_failed_on_adapter_error(
    database_url: str, _run_migrations: None, monkeypatch: object
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        run_id = await _seed_queued(factory)

        class _BoomAdapter:
            import_type = ImportType.GO_ONTOLOGY

            async def run(self, rt):
                raise RuntimeError("kaboom")

        monkeypatch.setitem(worker_mod.IMPORT_ADAPTERS, ImportType.GO_ONTOLOGY, _BoomAdapter())
        with pytest.raises(RuntimeError):
            await worker_mod.run_import(_ctx(factory), str(run_id))

        async with AsyncUnitOfWork(factory) as uow:
            run = await SQLAlchemyImportRunRepository(uow).get(run_id)
            assert run.status is ImportStatus.FAILED
            assert "kaboom" in run.error
    finally:
        await engine.dispose()


async def test_worker_marks_failed_on_system_exit(
    database_url: str, _run_migrations: None, monkeypatch: object
) -> None:
    """SystemExit (raised by resolve_organism_id) is caught and turns the run FAILED."""
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        run_id = await _seed_queued(factory)

        class _SystemExitAdapter:
            import_type = ImportType.GO_ONTOLOGY

            async def run(self, rt):
                raise SystemExit("no organism")

        monkeypatch.setitem(
            worker_mod.IMPORT_ADAPTERS, ImportType.GO_ONTOLOGY, _SystemExitAdapter()
        )
        with pytest.raises(SystemExit):
            await worker_mod.run_import(_ctx(factory), str(run_id))

        async with AsyncUnitOfWork(factory) as uow:
            run = await SQLAlchemyImportRunRepository(uow).get(run_id)
            assert run.status is ImportStatus.FAILED
            assert "no organism" in run.error
    finally:
        await engine.dispose()


async def test_di_smoke(database_url, _run_migrations) -> None:
    """create_container resolves import use cases and ArqJobEnqueuer without touching Redis."""
    from protcellar.application.imports.job_enqueuer import JobEnqueuer
    from protcellar.application.imports.start_import import StartImport
    from protcellar.application.imports.store_upload import StoreUpload
    from protcellar.infrastructure.di.container import create_container
    from protcellar.infrastructure.persistence.settings import DatabaseSettings

    container = create_container(DatabaseSettings(database_url=database_url, _env_file=None))  # type: ignore[call-arg]
    # These must resolve without error (and without connecting to Redis)
    _start = container[StartImport]
    _store = container[StoreUpload]
    _enqueuer = container[JobEnqueuer]
    assert _start is not None
    assert _store is not None
    assert _enqueuer is not None
