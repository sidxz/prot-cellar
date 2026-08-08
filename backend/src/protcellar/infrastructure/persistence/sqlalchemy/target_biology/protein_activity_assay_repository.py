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
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import owned_by, readable_by


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
        """Read path only — ``readable_by``. For a caller that loads records in
        order to mutate and save them, use ``find_owned_by_protein`` instead.
        """
        stmt = (
            select(ProteinActivityAssayModel)
            .where(
                readable_by(ProteinActivityAssayModel, workspace_id),
                ProteinActivityAssayModel.protein_id == protein_id,
            )
            .order_by(ProteinActivityAssayModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def find_owned_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[ProteinActivityAssay]:
        """The mutation-safe twin of ``find_by_protein`` — ``owned_by``, for the
        bulk-import load-then-update-then-save loop. A shared record is never
        found here, no matter what ``workspace_id`` a future caller passes.
        """
        stmt = (
            select(ProteinActivityAssayModel)
            .where(
                owned_by(ProteinActivityAssayModel, workspace_id),
                ProteinActivityAssayModel.protein_id == protein_id,
            )
            .order_by(ProteinActivityAssayModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
