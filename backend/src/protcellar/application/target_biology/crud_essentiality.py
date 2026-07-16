"""Single-record CRUD for Essentiality (admin-only writes).

Groups Create/Update/Delete for one record type in one module — they are small
and tightly coupled. Reads live in ``get_gene_target_biology`` (the bundle).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.repository import EssentialityRepository


@dataclass(frozen=True, kw_only=True)
class CreateEssentialityCommand(Command):
    gene_id: uuid.UUID
    classification: EssentialityClass
    provenance: Provenance
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    extensions: dict[str, Any] | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateEssentialityCommand(Command):
    id: uuid.UUID
    classification: EssentialityClass
    provenance: Provenance
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, kw_only=True)
class DeleteEssentialityCommand(Command):
    id: uuid.UUID


class CreateEssentiality:
    def __init__(
        self, uow: UnitOfWork, repo: EssentialityRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateEssentialityCommand, auth: AuthContext | None = None
    ) -> Result[Essentiality, DomainError]:
        require_admin(auth)
        async with self._uow:
            record = Essentiality.create(
                workspace_id=GLOBAL_WORKSPACE_ID,
                gene_id=input.gene_id,
                classification=input.classification,
                provenance=input.provenance,
                condition=input.condition,
                method=input.method,
                confidence=input.confidence,
                extensions=input.extensions,
            )
            await self._repo.save(record)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(record)


class UpdateEssentiality:
    def __init__(
        self, uow: UnitOfWork, repo: EssentialityRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: UpdateEssentialityCommand, auth: AuthContext | None = None
    ) -> Result[Essentiality, DomainError]:
        require_admin(auth)
        async with self._uow:
            record = await self._repo.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, input.id)
            if record is None:
                return Failure(NotFoundError("Essentiality", str(input.id)))
            # Full-row replace of the mutable fields (inline editor sends them all).
            # extensions is intentionally left untouched — the UI doesn't edit it.
            record.update(
                classification=input.classification,
                provenance=input.provenance,
                condition=input.condition,
                method=input.method,
                confidence=input.confidence,
            )
            await self._repo.save(record)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(record)


class DeleteEssentiality:
    def __init__(self, uow: UnitOfWork, repo: EssentialityRepository) -> None:
        self._uow, self._repo = uow, repo

    async def __call__(
        self, input: DeleteEssentialityCommand, auth: AuthContext | None = None
    ) -> Result[None, DomainError]:
        require_admin(auth)
        async with self._uow:
            record = await self._repo.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, input.id)
            if record is None:
                return Failure(NotFoundError("Essentiality", str(input.id)))
            await self._repo.delete(GLOBAL_WORKSPACE_ID, input.id)
            await self._uow.commit()
        return Success(None)
