"""CreateFieldDef — declare one extra field on one target-biology record kind (admin)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import ConflictError, DomainError
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)
from protcellar.domain.workspace_config.extension_fields.repository import (
    ExtensionFieldDefRepository,
)


@dataclass(frozen=True, kw_only=True)
class CreateFieldDefCommand(Command):
    workspace_id: uuid.UUID
    kind: str
    name: str
    label: str
    field_type: ExtensionFieldType
    options: list[str] | None
    position: int
    show_in_table: bool


class CreateFieldDef:
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
        self, input: CreateFieldDefCommand, auth: AuthContext | None = None
    ) -> Result[ExtensionFieldDef, DomainError]:
        require_admin(auth)
        require_same_workspace(auth, input.workspace_id)

        async with self._uow:
            # Explicit pre-check so the 409 comes from a business rule, not a
            # bubbled-up IntegrityError off the (workspace_id, kind, name) index.
            existing = await self._repo.find_by_name(input.workspace_id, input.kind, input.name)
            if existing is not None:
                return Failure(
                    ConflictError(
                        f"Extension field {input.name!r} already exists for kind {input.kind!r}"
                    )
                )

            field_def = ExtensionFieldDef.create(
                workspace_id=input.workspace_id,
                kind=input.kind,
                name=input.name,
                label=input.label,
                field_type=input.field_type,
                options=input.options,
                position=input.position,
                show_in_table=input.show_in_table,
            )
            await self._repo.save(field_def)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(field_def)
