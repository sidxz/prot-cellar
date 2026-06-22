"""Import hub DI bindings."""

from __future__ import annotations

from typing import Any

from lagom import Container, Singleton
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.imports.get_import_run import GetImportRun
from protcellar.application.imports.job_enqueuer import JobEnqueuer
from protcellar.application.imports.list_import_runs import ListImportRuns
from protcellar.application.imports.start_import import StartImport
from protcellar.application.imports.store_upload import GetUpload, StoreUpload
from protcellar.infrastructure.ingestion.arq_enqueuer import ArqJobEnqueuer
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_upload_repository import (
    SQLAlchemyImportUploadRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_imports(container: Container) -> None:
    """Register all import-hub use cases and their repositories.

    UoW-sharing pattern (mirroring _protein_catalog.py): each factory lambda
    creates ONE ``AsyncUnitOfWork`` and passes the same instance to both the
    use case and its repository.  This guarantees they share a single
    SQLAlchemy session / transaction.
    """

    def _start_import(c: Any) -> StartImport:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return StartImport(
            uow=uow,
            run_repo=SQLAlchemyImportRunRepository(uow),
            dispatcher=c[EventDispatcher],
            enqueuer=c[JobEnqueuer],
        )

    def _list_import_runs(c: Any) -> ListImportRuns:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return ListImportRuns(uow=uow, run_repo=SQLAlchemyImportRunRepository(uow))

    def _get_import_run(c: Any) -> GetImportRun:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return GetImportRun(uow=uow, run_repo=SQLAlchemyImportRunRepository(uow))

    def _store_upload(c: Any) -> StoreUpload:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return StoreUpload(uow=uow, upload_repo=SQLAlchemyImportUploadRepository(uow))

    def _get_upload(c: Any) -> GetUpload:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return GetUpload(uow=uow, upload_repo=SQLAlchemyImportUploadRepository(uow))

    # JobEnqueuer as a singleton: one lazy pool per process.
    container.define(JobEnqueuer, Singleton(ArqJobEnqueuer))  # type: ignore[type-abstract]

    container.define(StartImport, _start_import)
    container.define(ListImportRuns, _list_import_runs)
    container.define(GetImportRun, _get_import_run)
    container.define(StoreUpload, _store_upload)
    container.define(GetUpload, _get_upload)
