"""SQLAlchemy CrispriStrain repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.repository import CrispriStrainRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    CrispriStrainModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import owned_by, readable_by


class SQLAlchemyCrispriStrainRepository(
    SQLAlchemyRepository[CrispriStrain, CrispriStrainModel], CrispriStrainRepository
):
    model_class = CrispriStrainModel

    def _to_domain(self, model: CrispriStrainModel) -> CrispriStrain:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None
        return CrispriStrain(
            id=model.id,
            workspace_id=model.workspace_id,
            name=model.name,
            target_gene_id=model.target_gene_id,
            provenance=provenance,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: CrispriStrain) -> CrispriStrainModel:
        return CrispriStrainModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            name=aggregate.name,
            target_gene_id=aggregate.target_gene_id,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(self, model: CrispriStrainModel, aggregate: CrispriStrain) -> None:
        model.name = aggregate.name
        model.target_gene_id = aggregate.target_gene_id
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_gene(
        self, workspace_id: uuid.UUID, target_gene_id: uuid.UUID
    ) -> list[CrispriStrain]:
        """Read path only — ``readable_by``. For a caller that loads records in
        order to mutate and save them, use ``find_owned_by_gene`` instead.
        """
        stmt = (
            select(CrispriStrainModel)
            .where(
                readable_by(CrispriStrainModel, workspace_id),
                CrispriStrainModel.target_gene_id == target_gene_id,
            )
            .order_by(CrispriStrainModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def find_owned_by_gene(
        self, workspace_id: uuid.UUID, target_gene_id: uuid.UUID
    ) -> list[CrispriStrain]:
        """The mutation-safe twin of ``find_by_gene`` — ``owned_by``, for the
        bulk-import load-then-update-then-save loop. A shared record is never
        found here, no matter what ``workspace_id`` a future caller passes.
        """
        stmt = (
            select(CrispriStrainModel)
            .where(
                owned_by(CrispriStrainModel, workspace_id),
                CrispriStrainModel.target_gene_id == target_gene_id,
            )
            .order_by(CrispriStrainModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
