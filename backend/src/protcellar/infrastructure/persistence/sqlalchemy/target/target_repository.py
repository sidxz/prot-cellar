"""SQLAlchemy Target repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.repository import TargetRepository
from protcellar.domain.target.target import Target, TargetComponent
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._xref_json import (
    xrefs_from_json,
    xrefs_to_json,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import (
    TargetComponentModel,
    TargetModel,
)


class SQLAlchemyTargetRepository(SQLAlchemyRepository[Target, TargetModel], TargetRepository):
    model_class = TargetModel

    def _to_domain(self, model: TargetModel) -> Target:
        return Target(
            id=model.id,
            workspace_id=model.workspace_id,
            pref_name=model.pref_name,
            target_type=TargetType(model.target_type),
            components=[
                TargetComponent(
                    id=c.id,
                    protein_id=c.protein_id,
                    relationship=ComponentRelationship(c.relationship),
                )
                for c in model.components
            ],
            organism_id=model.organism_id,
            chembl_id=model.chembl_id,
            pharmacological_class=model.pharmacological_class,
            cross_references=xrefs_from_json(model.cross_references),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Target) -> TargetModel:
        model = TargetModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            pref_name=aggregate.pref_name,
            target_type=aggregate.target_type.value,
            organism_id=aggregate.organism_id,
            chembl_id=aggregate.chembl_id,
            pharmacological_class=aggregate.pharmacological_class,
            cross_references=xrefs_to_json(aggregate.cross_references) or None,
            version=aggregate.version,
        )
        model.components = [
            self._component_to_model(c, i) for i, c in enumerate(aggregate.components)
        ]
        return model

    def _update_model(self, model: TargetModel, aggregate: Target) -> None:
        model.pref_name = aggregate.pref_name
        model.target_type = aggregate.target_type.value
        model.organism_id = aggregate.organism_id
        model.chembl_id = aggregate.chembl_id
        model.pharmacological_class = aggregate.pharmacological_class
        model.cross_references = xrefs_to_json(aggregate.cross_references) or None
        # Replace the components collection wholesale (delete-orphan handles removals).
        model.components = [
            self._component_to_model(c, i) for i, c in enumerate(aggregate.components)
        ]

    @staticmethod
    def _component_to_model(c: TargetComponent, position: int) -> TargetComponentModel:
        return TargetComponentModel(
            id=c.id,
            protein_id=c.protein_id,
            relationship=c.relationship.value,
            position=position,
        )

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        target_type: TargetType | None = None,
        chembl_id: str | None = None,
    ) -> list[Target]:
        stmt = select(TargetModel).where(TargetModel.workspace_id == workspace_id)
        if target_type is not None:
            stmt = stmt.where(TargetModel.target_type == target_type.value)
        if chembl_id is not None:
            stmt = stmt.where(TargetModel.chembl_id == chembl_id)
        if cursor_id is not None:
            stmt = stmt.where(TargetModel.id > cursor_id)
        stmt = stmt.order_by(TargetModel.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
