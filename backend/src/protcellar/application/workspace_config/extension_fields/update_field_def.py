"""UpdateFieldDef — change label/shape of a declared extension field (admin).

``name`` is not a parameter — see ``ExtensionFieldDef.name`` (read-only property)
and the route body, which omits it entirely so sending it is a Pydantic
``extra="forbid"`` rejection rather than a hand-rolled guard here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin, require_same_workspace
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.sentinel import UNSET
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)
from protcellar.domain.workspace_config.extension_fields.repository import (
    ExtensionFieldDefRepository,
)


@dataclass(frozen=True, kw_only=True)
class UpdateFieldDefCommand(Command):
    workspace_id: uuid.UUID
    field_def_id: uuid.UUID
    label: str | None = None
    field_type: ExtensionFieldType | None = None
    # tri-state: UNSET = not sent (keep current), None = explicitly cleared —
    # ``options`` is the one field where ``None`` is itself a valid domain value
    # (a non-enum field carries none), so a plain ``None`` default can't tell
    # "left alone" apart from "cleared".
    options: list[str] | None | object = UNSET
    position: int | None = None
    show_in_table: bool | None = None


class UpdateFieldDef:
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
        self, input: UpdateFieldDefCommand, auth: AuthContext | None = None
    ) -> Result[ExtensionFieldDef, DomainError]:
        require_admin(auth)
        require_same_workspace(auth, input.workspace_id)

        async with self._uow:
            field_def = await self._repo.find_owned(input.workspace_id, input.field_def_id)
            if field_def is None:
                return Failure(NotFoundError("ExtensionFieldDef", str(input.field_def_id)))

            # ``update`` is total, not partial (see field_def.py) — every field not
            # sent in the request is re-supplied from the aggregate as loaded.
            # Collected through a ``dict[str, Any]`` (matching update_gene.py /
            # update_protein.py) rather than passed as direct kwargs: ``options``
            # is tri-state (UNSET | None | list[str]) and mypy cannot narrow an
            # ``is UNSET`` check against the ``Any``-typed sentinel, so a directly
            # typed kwarg trips strict mode even though the value is correct.
            fields: dict[str, Any] = {
                "label": input.label if input.label is not None else field_def.label,
                "field_type": (
                    input.field_type if input.field_type is not None else field_def.field_type
                ),
                "options": field_def.options if input.options is UNSET else input.options,
                "position": input.position if input.position is not None else field_def.position,
                "show_in_table": (
                    input.show_in_table
                    if input.show_in_table is not None
                    else field_def.show_in_table
                ),
            }
            field_def.update(**fields)
            await self._repo.save(field_def)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(field_def)
