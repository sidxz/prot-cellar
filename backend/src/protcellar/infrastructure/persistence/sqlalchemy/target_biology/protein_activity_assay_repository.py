"""SQLAlchemy ProteinActivityAssay repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.repository import ProteinActivityAssayRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    ProteinActivityAssayModel,
)


class SQLAlchemyProteinActivityAssayRepository(
    SQLAlchemyRepository[ProteinActivityAssay, ProteinActivityAssayModel],
    ProteinActivityAssayRepository,
):
    model_class = ProteinActivityAssayModel

    def _to_domain(self, model: ProteinActivityAssayModel) -> ProteinActivityAssay:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None
        return ProteinActivityAssay(
            id=model.id,
            workspace_id=model.workspace_id,
            protein_id=model.protein_id,
            activity_measured=model.activity_measured,
            provenance=provenance,
            readout=model.readout,
            throughput=model.throughput,
            condition=model.condition,
            method=model.method,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: ProteinActivityAssay) -> ProteinActivityAssayModel:
        return ProteinActivityAssayModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            protein_id=aggregate.protein_id,
            activity_measured=aggregate.activity_measured,
            readout=aggregate.readout,
            throughput=aggregate.throughput,
            condition=aggregate.condition,
            method=aggregate.method,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(
        self, model: ProteinActivityAssayModel, aggregate: ProteinActivityAssay
    ) -> None:
        model.activity_measured = aggregate.activity_measured
        model.readout = aggregate.readout
        model.throughput = aggregate.throughput
        model.condition = aggregate.condition
        model.method = aggregate.method
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[ProteinActivityAssay]:
        stmt = (
            select(ProteinActivityAssayModel)
            .where(
                ProteinActivityAssayModel.workspace_id == workspace_id,
                ProteinActivityAssayModel.protein_id == protein_id,
            )
            .order_by(ProteinActivityAssayModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
