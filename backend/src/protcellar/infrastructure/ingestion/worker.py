"""arq background worker for import jobs.

Entrypoint for arq::

    arq protcellar.infrastructure.ingestion.worker.WorkerSettings

The ``run_import`` function is the single task the worker executes.
``IMPORT_ADAPTERS`` is re-exported from import_adapters so that tests can
monkeypatch ``worker.IMPORT_ADAPTERS`` without touching the adapter registry
module directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.service_auth import ServiceAuth
from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.ingestion.arq_enqueuer import redis_settings_from_env

# Re-export so tests can monkeypatch worker.IMPORT_ADAPTERS
from protcellar.infrastructure.ingestion.import_adapters import IMPORT_ADAPTERS  # noqa: F401
from protcellar.infrastructure.ingestion.import_adapters import ImportRuntime
from protcellar.infrastructure.messaging.audit_event_handler import AuditEventHandler
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.database import create_engine_and_sessionmaker
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.imports.db_progress_reporter import (
    ImportRunProgressReporter,
)
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_upload_repository import (
    SQLAlchemyImportUploadRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


async def run_import(ctx: dict, import_run_id: str) -> None:
    """Execute a queued import run.

    Called by arq with ``ctx`` containing:
    - ``session_factory``: ``async_sessionmaker``
    - ``dispatcher``: :class:`EventDispatcher`

    The function:
    1. Loads the :class:`ImportRun` and transitions it to RUNNING.
    2. Resolves the matching :class:`ImportAdapter` from ``IMPORT_ADAPTERS``.
    3. Builds an :class:`ImportRuntime` and runs the adapter.
    4. Marks the run SUCCEEDED (or FAILED on error) and saves.

    **Exception handling:** catches ``(Exception, SystemExit)`` so that
    ``SystemExit`` raised by ``resolve_organism_id`` (when a tax_id resolves to
    no organism) is captured and stored as a FAILED run rather than crashing the
    worker.  ``asyncio.CancelledError`` and ``KeyboardInterrupt`` are
    intentionally NOT caught.
    """
    session_factory: async_sessionmaker = ctx["session_factory"]
    dispatcher: EventDispatcher = ctx["dispatcher"]

    run_id = uuid.UUID(import_run_id)

    # --- 1. Load run and transition to RUNNING ---
    async with AsyncUnitOfWork(session_factory) as uow:
        repo = SQLAlchemyImportRunRepository(uow)
        run = await repo.get(run_id)
        if run is None:
            raise RuntimeError(f"ImportRun {run_id} not found")
        run.start()
        await repo.save(run)
        events = await uow.commit()
    await dispatcher.dispatch_all(events)

    # --- 2. Resolve adapter ---
    adapter = IMPORT_ADAPTERS[run.import_type]

    # --- 3. Build load_upload callable ---
    async def _load_upload(upload_id: uuid.UUID) -> bytes:
        async with AsyncUnitOfWork(session_factory) as _uow:
            upload_repo = SQLAlchemyImportUploadRepository(_uow)
            upload = await upload_repo.get(upload_id)
            if upload is None:
                raise RuntimeError(f"ImportUpload {upload_id} not found")
            return upload.data

    # --- 4. Build ImportRuntime ---
    rt = ImportRuntime(
        session_factory=session_factory,
        dispatcher=dispatcher,
        reporter=ImportRunProgressReporter(run.id, session_factory),
        params=run.params,
        auth=ServiceAuth(),
        load_upload=_load_upload,
    )

    # --- 5. Run adapter and handle outcome ---
    try:
        summary = await adapter.run(rt)
    except (Exception, SystemExit) as exc:
        # Best-effort: reload and mark FAILED so the run record reflects the error.
        try:
            async with AsyncUnitOfWork(session_factory) as uow:
                repo = SQLAlchemyImportRunRepository(uow)
                failed_run = await repo.get(run_id)
                if failed_run is not None:
                    failed_run.fail(repr(exc))
                    await repo.save(failed_run)
                    fail_events = await uow.commit()
            await dispatcher.dispatch_all(fail_events)
        except Exception:
            pass  # Do not mask the original exception
        raise  # Re-raise so arq logs the failure

    # --- 6. Reload and mark SUCCEEDED ---
    async with AsyncUnitOfWork(session_factory) as uow:
        repo = SQLAlchemyImportRunRepository(uow)
        done_run = await repo.get(run_id)
        if done_run is None:
            raise RuntimeError(f"ImportRun {run_id} vanished after adapter finished")
        done_run.succeed(summary)
        await repo.save(done_run)
        done_events = await uow.commit()
    await dispatcher.dispatch_all(done_events)


# ---------------------------------------------------------------------------
# WorkerSettings — used when launching arq from the CLI
# ---------------------------------------------------------------------------


async def _on_startup(ctx: dict) -> None:
    """Build engine, session factory, and wired dispatcher; store in ctx."""
    db_settings = DatabaseSettings()  # type: ignore[call-arg]
    engine, session_factory = create_engine_and_sessionmaker(db_settings)
    ctx["engine"] = engine
    ctx["session_factory"] = session_factory

    dispatcher = EventDispatcher()
    dispatcher.register(DomainEvent, AuditEventHandler(session_factory))
    ctx["dispatcher"] = dispatcher


async def _on_shutdown(ctx: dict) -> None:
    """Dispose the engine on shutdown."""
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """arq WorkerSettings — mirrors the lifespan wiring in ``interface/app.py``."""

    functions = [run_import]
    redis_settings = redis_settings_from_env()
    on_startup = _on_startup
    on_shutdown = _on_shutdown
