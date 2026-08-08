"""SQLAlchemy Essentiality repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.repository import EssentialityRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import GeneModel
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._bulk_query import query_page
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    EssentialityRecordModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import owned_by, readable_by


class SQLAlchemyEssentialityRepository(
    SQLAlchemyRepository[Essentiality, EssentialityRecordModel], EssentialityRepository
):
    model_class = EssentialityRecordModel

    def _to_domain(self, model: EssentialityRecordModel) -> Essentiality:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None  # provenance is always written on create
        return Essentiality(
            id=model.id,
            workspace_id=model.workspace_id,
            gene_id=model.gene_id,
            classification=EssentialityClass(model.classification),
            provenance=provenance,
            condition=model.condition,
            method=model.method,
            confidence=model.confidence,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Essentiality) -> EssentialityRecordModel:
        return EssentialityRecordModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            gene_id=aggregate.gene_id,
            classification=aggregate.classification.value,
            condition=aggregate.condition,
            method=aggregate.method,
            confidence=aggregate.confidence,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(self, model: EssentialityRecordModel, aggregate: Essentiality) -> None:
        model.classification = aggregate.classification.value
        model.condition = aggregate.condition
        model.method = aggregate.method
        model.confidence = aggregate.confidence
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Essentiality]:
        """Read path only — ``readable_by``. For a caller that loads records in
        order to mutate and save them, use ``find_owned_by_gene`` instead.
        """
        stmt = (
            select(EssentialityRecordModel)
            .where(
                readable_by(EssentialityRecordModel, workspace_id),
                EssentialityRecordModel.gene_id == gene_id,
            )
            .order_by(EssentialityRecordModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def list_paginated(
        self,
        workspace_id: uuid.UUID,
        *,
        gene_ids: Sequence[uuid.UUID] = (),
        protein_ids: Sequence[uuid.UUID] = (),
        organism_id: uuid.UUID | None = None,
        strain_id: uuid.UUID | None = None,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[Essentiality]:
        """Bulk, cursor-paginated read across every gene — ``GET /target-biology/{kind}``.

        ``protein_ids`` is accepted but unused: every kind's ``list_paginated``
        shares one call shape so the ``RecordKind``-keyed dispatch in the bulk-list
        use case can call it uniformly.
        """
        models = await query_page(
            self._session,
            EssentialityRecordModel,
            EssentialityRecordModel.gene_id,
            parent=GeneModel,
            workspace_id=workspace_id,
            parent_ids=gene_ids,
            organism_id=organism_id,
            strain_id=strain_id,
            cursor_id=cursor_id,
            limit=limit,
        )
        return [self._to_domain_tracked(m) for m in models]

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[Essentiality]:
        """The mutation-safe twin of ``find_by_gene`` — ``owned_by``, for the
        bulk-import load-then-update-then-save loop. A shared record is never
        found here, no matter what ``workspace_id`` a future caller passes.
        """
        stmt = (
            select(EssentialityRecordModel)
            .where(
                owned_by(EssentialityRecordModel, workspace_id),
                EssentialityRecordModel.gene_id == gene_id,
            )
            .order_by(EssentialityRecordModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
