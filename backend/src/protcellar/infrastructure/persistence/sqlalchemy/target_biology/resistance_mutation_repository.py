"""SQLAlchemy ResistanceMutation repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target_biology.repository import ResistanceMutationRepository
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._compound_json import (
    compound_from_json,
    compound_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    ResistanceMutationModel,
)


class SQLAlchemyResistanceMutationRepository(
    SQLAlchemyRepository[ResistanceMutation, ResistanceMutationModel],
    ResistanceMutationRepository,
):
    model_class = ResistanceMutationModel

    def _to_domain(self, model: ResistanceMutationModel) -> ResistanceMutation:
        provenance = provenance_from_json(model.provenance)
        assert provenance is not None
        return ResistanceMutation(
            id=model.id,
            workspace_id=model.workspace_id,
            gene_id=model.gene_id,
            mutation=model.mutation,
            provenance=provenance,
            compound=compound_from_json(model.compound),
            mic_shift=model.mic_shift,
            parent_strain=model.parent_strain,
            protein_coordinate=model.protein_coordinate,
            method=model.method,
            extensions=dict(model.extensions or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: ResistanceMutation) -> ResistanceMutationModel:
        return ResistanceMutationModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            gene_id=aggregate.gene_id,
            mutation=aggregate.mutation,
            compound=compound_to_json(aggregate.compound),
            mic_shift=aggregate.mic_shift,
            parent_strain=aggregate.parent_strain,
            protein_coordinate=aggregate.protein_coordinate,
            method=aggregate.method,
            provenance=provenance_to_json(aggregate.provenance),
            extensions=aggregate.extensions or None,
            version=aggregate.version,
        )

    def _update_model(
        self, model: ResistanceMutationModel, aggregate: ResistanceMutation
    ) -> None:
        model.mutation = aggregate.mutation
        model.compound = compound_to_json(aggregate.compound)
        model.mic_shift = aggregate.mic_shift
        model.parent_strain = aggregate.parent_strain
        model.protein_coordinate = aggregate.protein_coordinate
        model.method = aggregate.method
        model.provenance = provenance_to_json(aggregate.provenance)
        model.extensions = aggregate.extensions or None

    async def find_by_gene(
        self, workspace_id: uuid.UUID, gene_id: uuid.UUID
    ) -> list[ResistanceMutation]:
        stmt = (
            select(ResistanceMutationModel)
            .where(
                ResistanceMutationModel.workspace_id == workspace_id,
                ResistanceMutationModel.gene_id == gene_id,
            )
            .order_by(ResistanceMutationModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
