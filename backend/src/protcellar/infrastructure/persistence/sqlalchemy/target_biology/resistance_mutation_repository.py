"""SQLAlchemy ResistanceMutation repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from protcellar.domain.target_biology.repository import ResistanceMutationRepository
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import GeneModel
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._bulk_query import query_page
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
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import owned_by, readable_by


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

    def _update_model(self, model: ResistanceMutationModel, aggregate: ResistanceMutation) -> None:
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
        """Read path only — ``readable_by``. For a caller that loads records in
        order to mutate and save them, use ``find_owned_by_gene`` instead.
        """
        stmt = (
            select(ResistanceMutationModel)
            .where(
                readable_by(ResistanceMutationModel, workspace_id),
                ResistanceMutationModel.gene_id == gene_id,
            )
            .order_by(ResistanceMutationModel.id)
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
    ) -> list[ResistanceMutation]:
        """Bulk, cursor-paginated read across every gene — ``GET /target-biology/{kind}``.

        ``protein_ids`` is accepted but unused: every kind's ``list_paginated``
        shares one call shape so the ``RecordKind``-keyed dispatch in the bulk-list
        use case can call it uniformly.
        """
        models = await query_page(
            self._session,
            ResistanceMutationModel,
            ResistanceMutationModel.gene_id,
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
    ) -> list[ResistanceMutation]:
        """The mutation-safe twin of ``find_by_gene`` — ``owned_by``, for the
        bulk-import load-then-update-then-save loop. A shared record is never
        found here, no matter what ``workspace_id`` a future caller passes.
        """
        stmt = (
            select(ResistanceMutationModel)
            .where(
                owned_by(ResistanceMutationModel, workspace_id),
                ResistanceMutationModel.gene_id == gene_id,
            )
            .order_by(ResistanceMutationModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
