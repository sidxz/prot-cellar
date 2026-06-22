"""StartImport use case — validate params, guard against duplicates, enqueue."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.imports.job_enqueuer import JobEnqueuer
from protcellar.application.imports.params import target_key, upload_ref_of, validate_params
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.imports.enums import ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.imports.repository import ImportRunRepository
from protcellar.domain.shared.errors import ConflictError, DomainError


@dataclass(frozen=True, kw_only=True)
class StartImportCommand:
    import_type: ImportType
    params: dict = field(default_factory=dict)


class StartImport:
    def __init__(
        self,
        uow: UnitOfWork,
        run_repo: ImportRunRepository,
        dispatcher: EventDispatcherProtocol,
        enqueuer: JobEnqueuer,
    ) -> None:
        self._uow = uow
        self._run_repo = run_repo
        self._dispatcher = dispatcher
        self._enqueuer = enqueuer

    async def __call__(
        self, cmd: StartImportCommand, auth: AuthContext | None = None
    ) -> Result[ImportRun, DomainError]:
        require_admin(auth)

        params = validate_params(cmd.import_type, cmd.params)
        tkey = target_key(cmd.import_type, params)

        # Reject if there's already an active (QUEUED/RUNNING) run for this target.
        active = await self._run_repo.find_active(cmd.import_type, tkey)
        if active is not None:
            return Failure(
                ConflictError(
                    f"An active import run already exists for {cmd.import_type}/{tkey}",
                    detail=f"active_run_id={active.id}",
                )
            )

        requested_by: uuid.UUID = auth.user_id  # type: ignore[union-attr]
        upload_ref = upload_ref_of(cmd.import_type, params)

        async with self._uow:
            run = ImportRun.create(
                import_type=cmd.import_type,
                params=params,
                target_key=tkey,
                requested_by=requested_by,
                upload_ref=upload_ref,
            )
            await self._run_repo.save(run)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        await self._enqueuer.enqueue_import(run.id)

        return Success(run)
