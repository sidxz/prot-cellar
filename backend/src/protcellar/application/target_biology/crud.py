"""Generic admin CRUD for the eight target-biology record types.

The persistence logic (guard → save/delete → commit → dispatch) is identical
across all record types, so it lives here once, keyed by ``RecordKind``. The
per-record specifics — typed request bodies, aggregate construction, and which
fields an update touches — live in the route layer.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import (
    ConcurrencyConflictError,
    DomainError,
    NotFoundError,
)


class RecordKind(StrEnum):
    ESSENTIALITY = "essentiality"
    VULNERABILITY = "vulnerability"
    HYPOMORPH = "hypomorph"
    CRISPRI_STRAIN = "crispri_strain"
    RESISTANCE_MUTATION = "resistance_mutation"
    PROTEIN_PRODUCTION = "protein_production"
    PROTEIN_ACTIVITY_ASSAY = "protein_activity_assay"
    UNPUBLISHED_STRUCTURE = "unpublished_structure"


# A repo keyed in the registry; every target-biology repo satisfies this.
Repos = dict[RecordKind, Any]


class CreateTargetBiologyRecord:
    def __init__(self, uow: UnitOfWork, repos: Repos, dispatcher: EventDispatcherProtocol) -> None:
        self._uow, self._repos, self._dispatcher = uow, repos, dispatcher

    async def __call__(
        self, kind: RecordKind, aggregate: AggregateRoot, auth: AuthContext | None = None
    ) -> Result[AggregateRoot, DomainError]:
        require_admin(auth)
        async with self._uow:
            await self._repos[kind].save(aggregate)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(aggregate)


class UpdateTargetBiologyRecord:
    def __init__(self, uow: UnitOfWork, repos: Repos, dispatcher: EventDispatcherProtocol) -> None:
        self._uow, self._repos, self._dispatcher = uow, repos, dispatcher

    async def __call__(
        self,
        kind: RecordKind,
        record_id: uuid.UUID,
        updates: dict[str, Any],
        auth: AuthContext | None = None,
        expected_version: int | None = None,
    ) -> Result[AggregateRoot, DomainError]:
        require_admin(auth)
        async with self._uow:
            record = await self._repos[kind].find_owned(
                auth.workspace_id,  # type: ignore[union-attr]
                record_id,
            )
            if record is None:
                return Failure(NotFoundError(kind.value, str(record_id)))
            # Opt-in: a caller that supplies no version keeps last-write-wins, so
            # importers and scripts are unaffected. The repository CAS stays as the
            # backstop for the race between this read and the save below.
            if expected_version is not None and record.version != expected_version:
                return Failure(
                    ConcurrencyConflictError(
                        kind.value,
                        str(record_id),
                        detail=(f"Expected version {expected_version}, found {record.version}"),
                    )
                )
            record.update(**updates)
            await self._repos[kind].save(record)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(record)


class DeleteTargetBiologyRecord:
    def __init__(self, uow: UnitOfWork, repos: Repos) -> None:
        self._uow, self._repos = uow, repos

    async def __call__(
        self, kind: RecordKind, record_id: uuid.UUID, auth: AuthContext | None = None
    ) -> Result[None, DomainError]:
        require_admin(auth)
        async with self._uow:
            record = await self._repos[kind].find_owned(
                auth.workspace_id,  # type: ignore[union-attr]
                record_id,
            )
            if record is None:
                return Failure(NotFoundError(kind.value, str(record_id)))
            workspace_id: uuid.UUID = auth.workspace_id  # type: ignore[union-attr]
            await self._repos[kind].delete(workspace_id, record_id)
            await self._uow.commit()
        return Success(None)
