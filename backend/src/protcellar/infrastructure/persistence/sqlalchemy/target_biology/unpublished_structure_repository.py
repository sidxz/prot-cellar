"""SQLAlchemy UnpublishedStructure repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.repository import UnpublishedStructureRepository
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._compound_json import (
    ligands_from_json,
    ligands_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    UnpublishedStructureModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import owned_by, readable_by


class SQLAlchemyUnpublishedStructureRepository(
    SQLAlchemyRepository[UnpublishedStructure, UnpublishedStructureModel],
    UnpublishedStructureRepository,
):
    model_class = UnpublishedStructureModel

    def _to_domain(self, model: UnpublishedStructureModel) -> UnpublishedStructure:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None
        return UnpublishedStructure(
            id=model.id,
            workspace_id=model.workspace_id,
            protein_id=model.protein_id,
            provenance=provenance,
            method=model.method,
            resolution=model.resolution,
            ligands=ligands_from_json(model.ligands),
            is_published=model.is_published,
            is_experimental=model.is_experimental,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: UnpublishedStructure) -> UnpublishedStructureModel:
        return UnpublishedStructureModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            protein_id=aggregate.protein_id,
            method=aggregate.method,
            resolution=aggregate.resolution,
            ligands=ligands_to_json(aggregate.ligands),
            is_published=aggregate.is_published,
            is_experimental=aggregate.is_experimental,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(
        self, model: UnpublishedStructureModel, aggregate: UnpublishedStructure
    ) -> None:
        model.method = aggregate.method
        model.resolution = aggregate.resolution
        model.ligands = ligands_to_json(aggregate.ligands)
        model.is_published = aggregate.is_published
        model.is_experimental = aggregate.is_experimental
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[UnpublishedStructure]:
        """Read path only — ``readable_by``. For a caller that loads records in
        order to mutate and save them, use ``find_owned_by_protein`` instead.
        """
        stmt = (
            select(UnpublishedStructureModel)
            .where(
                readable_by(UnpublishedStructureModel, workspace_id),
                UnpublishedStructureModel.protein_id == protein_id,
            )
            .order_by(UnpublishedStructureModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    async def find_owned_by_protein(
        self, workspace_id: uuid.UUID, protein_id: uuid.UUID
    ) -> list[UnpublishedStructure]:
        """The mutation-safe twin of ``find_by_protein`` — ``owned_by``, for the
        bulk-import load-then-update-then-save loop. A shared record is never
        found here, no matter what ``workspace_id`` a future caller passes.
        """
        stmt = (
            select(UnpublishedStructureModel)
            .where(
                owned_by(UnpublishedStructureModel, workspace_id),
                UnpublishedStructureModel.protein_id == protein_id,
            )
            .order_by(UnpublishedStructureModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
