"""SQLAlchemy Essentiality repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.repository import EssentialityRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    EssentialityRecordModel,
)


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
        stmt = (
            select(EssentialityRecordModel)
            .where(
                EssentialityRecordModel.workspace_id == workspace_id,
                EssentialityRecordModel.gene_id == gene_id,
            )
            .order_by(EssentialityRecordModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
