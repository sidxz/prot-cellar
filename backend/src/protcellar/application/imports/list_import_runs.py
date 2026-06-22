"""ListImportRuns query — paginated listing of import runs (newest-first)."""

from __future__ import annotations

from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import (
    PageResult,
    clamp_limit,
    encode_ts_cursor,
    parse_ts_cursor,
)
from protcellar.application.shared.query import Query
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.imports.repository import ImportRunRepository
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class ListImportRunsQuery(Query):
    cursor: str | None = None
    limit: int | None = None


class ListImportRuns:
    def __init__(self, run_repo: ImportRunRepository) -> None:
        self._run_repo = run_repo

    async def __call__(
        self, input: ListImportRunsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[ImportRun], DomainError]:
        require_authenticated(auth)

        effective_limit = clamp_limit(input.limit)
        parsed_cursor = parse_ts_cursor(input.cursor)

        runs = await self._run_repo.list(
            cursor=parsed_cursor,
            limit=effective_limit + 1,
        )

        next_cursor: str | None = None
        if len(runs) > effective_limit:
            runs = runs[:effective_limit]
            last = runs[-1]
            next_cursor = encode_ts_cursor(last.created_at, last.id)

        return Success(PageResult(items=runs, next_cursor=next_cursor))
