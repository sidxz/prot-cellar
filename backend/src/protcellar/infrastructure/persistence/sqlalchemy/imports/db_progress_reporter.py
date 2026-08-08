"""DB-backed ProgressReporter that persists progress to an ImportRun aggregate.

Each call opens a short AsyncUnitOfWork, loads the ImportRun, applies the
mutation, saves, and commits.  ``advance`` is throttled to at most one DB write
per second (using ``time.monotonic()``), except that the very last/explicit call
always writes.
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

_THROTTLE_SECONDS = 1.0


class ImportRunProgressReporter:
    """Persists import progress into an existing ImportRun row.

    Parameters
    ----------
    import_run_id:
        The UUID of an already-created ImportRun (must exist in the DB).
    session_factory:
        An ``async_sessionmaker`` used to open short-lived UoW transactions.
    """

    def __init__(
        self,
        import_run_id: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._import_run_id = import_run_id
        self._session_factory = session_factory
        self._last_advance_write: float = 0.0

    async def phase(self, label: str) -> None:
        """Persist a phase-name change immediately (not throttled)."""
        async with AsyncUnitOfWork(self._session_factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            run = await repo.get_owned(self._import_run_id)
            if run is None:
                return
            run.record_progress(phase=label)
            await repo.save(run)
            await uow.commit()

    async def advance(self, processed: int, total: int | None = None) -> None:
        """Persist progress, throttled to at most one write per second.

        The throttle is bypassed when *total* is provided AND *processed == total*
        (i.e., the final chunk / completion call always writes).
        """
        now = time.monotonic()
        is_final = total is not None and processed >= total
        if not is_final and (now - self._last_advance_write) < _THROTTLE_SECONDS:
            return
        async with AsyncUnitOfWork(self._session_factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            run = await repo.get_owned(self._import_run_id)
            if run is None:
                return
            run.record_progress(processed=processed, total=total)
            await repo.save(run)
            await uow.commit()
        self._last_advance_write = time.monotonic()

    async def source_version(self, version: str | None) -> None:
        """Persist the source version string immediately (not throttled)."""
        async with AsyncUnitOfWork(self._session_factory) as uow:
            repo = SQLAlchemyImportRunRepository(uow)
            run = await repo.get_owned(self._import_run_id)
            if run is None:
                return
            run.set_source_version(version)
            await repo.save(run)
            await uow.commit()
