"""ListTargetBiologyRecords — bulk, cursor-paginated read of one record kind
across every gene or protein. ``GET /target-biology/{kind}``.

The per-gene/-protein bundles (``GetGeneTargetBiology``/``GetProteinTargetBiology``)
answer "everything about this one gene"; this answers "every essentiality record
in this organism" — the read a consumer needs when working across a whole
proteome instead of one gene at a time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.application.target_biology.crud import RecordKind, Repos
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class ListTargetBiologyRecordsQuery(Query):
    kind: RecordKind
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    gene_ids: tuple[uuid.UUID, ...] = ()
    protein_ids: tuple[uuid.UUID, ...] = ()
    organism_id: uuid.UUID | None = None
    strain_id: uuid.UUID | None = None


class ListTargetBiologyRecords:
    def __init__(self, uow: UnitOfWork, repos: Repos) -> None:
        self._uow = uow
        self._repos = repos

    async def __call__(
        self, input: ListTargetBiologyRecordsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[AggregateRoot], DomainError]:
        require_authenticated(auth)
        workspace_id: uuid.UUID = auth.workspace_id  # type: ignore[union-attr]
        async with self._uow:
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            items = await self._repos[input.kind].list_paginated(
                workspace_id,
                gene_ids=input.gene_ids,
                protein_ids=input.protein_ids,
                organism_id=input.organism_id,
                strain_id=input.strain_id,
                cursor_id=input.cursor_id,
                limit=fetch_limit,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(items) > effective_limit:
                items = items[:effective_limit]
                next_cursor = str(items[-1].id)

            return Success(PageResult(items=items, next_cursor=next_cursor))
