"""DeleteFieldDef — retract a declared extension field (admin).

Mirrors ``tagging/delete_tag.py``: the aggregate has no ``delete()`` of its own
(a declaration doesn't accrue lifecycle state worth modelling on the aggregate),
so the tombstone event is registered here, from the use case.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.workspace_config.extension_fields.events import ExtensionFieldDefDeleted
from protcellar.domain.workspace_config.extension_fields.repository import (
    ExtensionFieldDefRepository,
)


@dataclass(frozen=True, kw_only=True)
class DeleteFieldDefCommand(Command):
    workspace_id: uuid.UUID
    field_def_id: uuid.UUID


class DeleteFieldDef:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: ExtensionFieldDefRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: DeleteFieldDefCommand, auth: AuthContext | None = None
    ) -> Result[None, DomainError]:
        require_admin(auth)
        require_same_workspace(auth, input.workspace_id)

        async with self._uow:
            field_def = await self._repo.find_owned(input.workspace_id, input.field_def_id)
            if field_def is None:
                return Failure(NotFoundError("ExtensionFieldDef", str(input.field_def_id)))

            # find_owned already tracked field_def with the UoW (it returns via the
            # base repo's _to_domain_tracked), so the event registered below is
            # collected on commit without an extra self._uow.track() call here —
            # deliberately not repeating delete_tag.py's redundant one, which
            # exists only because UnitOfWork (the application Protocol) doesn't
            # declare .track() and every such call is a pre-existing mypy error.
            field_def.register_event(
                ExtensionFieldDefDeleted(
                    aggregate_id=field_def.id,
                    aggregate_type="ExtensionFieldDef",
                    workspace_id=input.workspace_id,
                    kind=field_def.kind,
                    name=field_def.name,
                )
            )
            await self._repo.delete(input.workspace_id, field_def.id)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(None)
