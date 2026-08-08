"""Shared cursor-paginated, workspace-scoped query for the bulk target-biology
list route (``GET /target-biology/{kind}``).

Every one of the eight repositories calls this once from its ``list_paginated``,
instead of the parent join and the keyset walk being copy-pasted eight times.
``organism_id``/``strain_id`` live on the parent gene or protein row, not on the
record itself (see the module docstring on ``target_biology/models.py``), so
scoping by either means joining to it — the same ``organism_id``/``strain_id``
columns ``/genes`` and ``/proteins`` already filter directly, reached here
through the record's ``gene_id`` / ``target_gene_id`` / ``protein_id``.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import (
    GeneModel,
    ProteinModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import readable_by


async def query_page(
    session: AsyncSession,
    model: Any,
    parent_id_column: Any,
    *,
    parent: type[GeneModel] | type[ProteinModel],
    workspace_id: uuid.UUID,
    parent_ids: Sequence[uuid.UUID] = (),
    organism_id: uuid.UUID | None = None,
    strain_id: uuid.UUID | None = None,
    cursor_id: uuid.UUID | None = None,
    limit: int | None = None,
) -> Sequence[Any]:
    """``readable_by``-scoped page of ``model`` rows, keyset-paginated on ``id``.

    ``parent_id_column`` is the record's own column that names the parent (e.g.
    ``EssentialityRecordModel.gene_id``); ``parent`` is the model it points at
    (``GeneModel``/``ProteinModel``). A join is only added when organism/strain
    filtering is actually requested — every other caller pays for one query, no
    join.
    """
    stmt = select(model).where(readable_by(model, workspace_id))
    if parent_ids:
        stmt = stmt.where(parent_id_column.in_(parent_ids))
    if organism_id is not None or strain_id is not None:
        stmt = stmt.join(parent, parent.id == parent_id_column).where(
            readable_by(parent, workspace_id)
        )
        if organism_id is not None:
            stmt = stmt.where(parent.organism_id == organism_id)
        if strain_id is not None:
            stmt = stmt.where(parent.strain_id == strain_id)
    if cursor_id is not None:
        stmt = stmt.where(model.id > cursor_id)
    stmt = stmt.order_by(model.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()
