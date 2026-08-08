"""SQLAlchemy ProteinProduction repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.repository import ProteinProductionRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    ProteinProductionModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import owned_by, readable_by


class SQLAlchemyProteinProductionRepository(
    SQLAlchemyRepository[ProteinProduction, ProteinProductionModel],
    ProteinProductionRepository,
):
    model_class = ProteinProductionModel

    def _to_domain(self, model: ProteinProductionModel) -> ProteinProduction:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None
        return ProteinProduction(
            id=model.id,
            workspace_id=model.workspace_id,
            protein_id=model.protein_id,
            status=model.status,
            provenance=provenance,
            expression_host=model.expression_host,
            purity=model.purity,
            condition=model.condition,
            method=model.method,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: ProteinProduction) -> ProteinProductionModel:
        return ProteinProductionModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            protein_id=aggregate.protein_id,
            status=aggregate.status,
            expression_host=aggregate.expression_host,
            purity=aggregate.purity,
            condition=aggregate.condition,
            method=aggregate.method,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(self, model: ProteinProductionModel, aggregate: ProteinProduction) -> None:
        model.status = aggregate.status
        model.expression_host = aggregate.expression_host
        model.purity = aggregate.purity
        model.condition = aggregate.condition
        model.method = aggregate.method
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[ProteinProduction]:
        """Read path only — ``readable_by``. For a caller that loads records in
        order to mutate and save them, use ``find_owned_by_protein`` instead.
        """
        stmt = (
            select(ProteinProductionModel)
            .where(
                readable_by(ProteinProductionModel, workspace_id),
                ProteinProductionModel.protein_id == protein_id,
            )
            .order_by(ProteinProductionModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def find_owned_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[ProteinProduction]:
        """The mutation-safe twin of ``find_by_protein`` — ``owned_by``, for the
        bulk-import load-then-update-then-save loop. A shared record is never
        found here, no matter what ``workspace_id`` a future caller passes.
        """
        stmt = (
            select(ProteinProductionModel)
            .where(
                owned_by(ProteinProductionModel, workspace_id),
                ProteinProductionModel.protein_id == protein_id,
            )
            .order_by(ProteinProductionModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
