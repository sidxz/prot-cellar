"""SQLAlchemy GO ontology repository — chunked bulk upsert + version query.

GO is large reference data (~47k terms, ~80k edges), so this bypasses the
per-aggregate UoW path and uses Postgres bulk upserts, chunked to stay under
the 65 535 bind-parameter ceiling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from protcellar.domain.gene_ontology.go_term import GoEdge, GoTerm
from protcellar.infrastructure.persistence.sqlalchemy.gene_ontology.models import (
    GoEdgeModel,
    GoTermModel,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

_CHUNK = 5000


class SQLAlchemyGoOntologyRepository:
    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

    async def upsert_terms(self, terms: list[GoTerm], *, source_version: str) -> int:
        now = datetime.now(UTC)
        for start in range(0, len(terms), _CHUNK):
            batch = terms[start : start + _CHUNK]
            rows = [
                {
                    "id": uuid.uuid4(),
                    "go_id": t.go_id,
                    "name": t.name,
                    "namespace": t.namespace,
                    "definition": t.definition,
                    "is_obsolete": t.is_obsolete,
                    "replaced_by": t.replaced_by,
                    "source": "go",
                    "source_version": source_version,
                    "imported_at": now,
                }
                for t in batch
            ]
            stmt = pg_insert(GoTermModel).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["go_id"],
                set_={
                    "name": stmt.excluded.name,
                    "namespace": stmt.excluded.namespace,
                    "definition": stmt.excluded.definition,
                    "is_obsolete": stmt.excluded.is_obsolete,
                    "replaced_by": stmt.excluded.replaced_by,
                    "source_version": stmt.excluded.source_version,
                    "imported_at": stmt.excluded.imported_at,
                    "updated_at": now,
                },
            )
            await self._session.execute(stmt)
        return len(terms)

    async def replace_edges(self, edges: list[GoEdge]) -> int:
        await self._session.execute(sa_delete(GoEdgeModel))
        for start in range(0, len(edges), _CHUNK):
            batch = edges[start : start + _CHUNK]
            rows = [
                {
                    "id": uuid.uuid4(),
                    "child_go_id": e.child_go_id,
                    "parent_go_id": e.parent_go_id,
                    "relation": e.relation,
                }
                for e in batch
            ]
            await self._session.execute(pg_insert(GoEdgeModel).values(rows))
        return len(edges)

    async def find_term(self, go_id: str) -> GoTerm | None:
        model = (
            await self._session.execute(select(GoTermModel).where(GoTermModel.go_id == go_id))
        ).scalar_one_or_none()
        if model is None:
            return None
        return GoTerm(
            go_id=model.go_id,
            name=model.name,
            namespace=model.namespace,
            definition=model.definition,
            is_obsolete=model.is_obsolete,
            replaced_by=model.replaced_by,
        )

    async def latest_source_version(self) -> str | None:
        result = await self._session.execute(select(func.max(GoTermModel.source_version)))
        return result.scalar_one_or_none()
