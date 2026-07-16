"""SQLAlchemy Hypomorph repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.repository import HypomorphRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import HypomorphModel


class SQLAlchemyHypomorphRepository(
    SQLAlchemyRepository[Hypomorph, HypomorphModel], HypomorphRepository
):
    model_class = HypomorphModel

    def _to_domain(self, model: HypomorphModel) -> Hypomorph:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None
        return Hypomorph(
            id=model.id,
            workspace_id=model.workspace_id,
            gene_id=model.gene_id,
            growth_defect=model.growth_defect,
            provenance=provenance,
            knockdown_strain_id=model.knockdown_strain_id,
            growth_defect_severity=model.growth_defect_severity,
            condition=model.condition,
            method=model.method,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Hypomorph) -> HypomorphModel:
        return HypomorphModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            gene_id=aggregate.gene_id,
            growth_defect=aggregate.growth_defect,
            knockdown_strain_id=aggregate.knockdown_strain_id,
            growth_defect_severity=aggregate.growth_defect_severity,
            condition=aggregate.condition,
            method=aggregate.method,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(self, model: HypomorphModel, aggregate: Hypomorph) -> None:
        model.growth_defect = aggregate.growth_defect
        model.knockdown_strain_id = aggregate.knockdown_strain_id
        model.growth_defect_severity = aggregate.growth_defect_severity
        model.condition = aggregate.condition
        model.method = aggregate.method
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_gene(self, workspace_id: uuid.UUID, gene_id: uuid.UUID) -> list[Hypomorph]:
        stmt = (
            select(HypomorphModel)
            .where(
                HypomorphModel.workspace_id == workspace_id,
                HypomorphModel.gene_id == gene_id,
            )
            .order_by(HypomorphModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
