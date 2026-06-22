"""GetImportRun query — retrieve a single import run by ID."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.imports.repository import ImportRunRepository
from protcellar.domain.shared.errors import DomainError, NotFoundError


@dataclass(frozen=True, kw_only=True)
class GetImportRunQuery(Query):
    import_run_id: uuid.UUID


class GetImportRun:
    def __init__(self, run_repo: ImportRunRepository) -> None:
        self._run_repo = run_repo

    async def __call__(
        self, input: GetImportRunQuery, auth: AuthContext | None = None
    ) -> Result[ImportRun, DomainError]:
        require_authenticated(auth)

        run = await self._run_repo.get(input.import_run_id)
        if run is None:
            return Failure(NotFoundError("ImportRun", str(input.import_run_id)))
        return Success(run)
