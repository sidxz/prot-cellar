"""SQLAlchemy Organism repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.organism import Organism, OrganismName
from protcellar.domain.taxonomy.repository import OrganismRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import (
    OrganismModel,
    OrganismNameModel,
)


class SQLAlchemyOrganismRepository(
    SQLAlchemyRepository[Organism, OrganismModel], OrganismRepository
):
    model_class = OrganismModel

    def _to_domain(self, model: OrganismModel) -> Organism:
        org = Organism(
            id=model.id,
            ncbi_tax_id=model.ncbi_tax_id,
            parent_id=model.parent_id,
            rank=model.rank,
            scientific_name=model.scientific_name,
            division=model.division,
            is_merged=model.is_merged,
            merged_into_id=model.merged_into_id,
            is_deleted=model.is_deleted,
            source=OrganismSource(model.source),
            source_version=model.source_version,
            names=[
                OrganismName(
                    id=n.id,
                    name=n.name,
                    name_class=NameClass(n.name_class),
                    unique_name=n.unique_name,
                    is_preferred=n.is_preferred,
                )
                for n in model.names
            ],
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
        return org

    def _to_model(self, aggregate: Organism) -> OrganismModel:
        model = OrganismModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            ncbi_tax_id=aggregate.ncbi_tax_id,
            parent_id=aggregate.parent_id,
            rank=aggregate.rank,
            scientific_name=aggregate.scientific_name,
            division=aggregate.division,
            is_merged=aggregate.is_merged,
            merged_into_id=aggregate.merged_into_id,
            is_deleted=aggregate.is_deleted,
            source=aggregate.source.value,
            source_version=aggregate.source_version,
            version=aggregate.version,
        )
        model.names = [self._name_to_model(n) for n in aggregate.names]
        return model

    def _update_model(self, model: OrganismModel, aggregate: Organism) -> None:
        model.ncbi_tax_id = aggregate.ncbi_tax_id
        model.parent_id = aggregate.parent_id
        model.rank = aggregate.rank
        model.scientific_name = aggregate.scientific_name
        model.division = aggregate.division
        model.is_merged = aggregate.is_merged
        model.merged_into_id = aggregate.merged_into_id
        model.is_deleted = aggregate.is_deleted
        model.source = aggregate.source.value
        model.source_version = aggregate.source_version
        # Replace the names collection wholesale (delete-orphan handles removals)
        model.names = [self._name_to_model(n) for n in aggregate.names]

    @staticmethod
    def _name_to_model(n: OrganismName) -> OrganismNameModel:
        return OrganismNameModel(
            id=n.id,
            name=n.name,
            name_class=n.name_class.value,
            unique_name=n.unique_name,
            is_preferred=n.is_preferred,
        )

    async def find_by_tax_id(self, tax_id: int) -> Organism | None:
        stmt = select(OrganismModel).where(OrganismModel.ncbi_tax_id == tax_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_children(self, parent_id: uuid.UUID) -> list[Organism]:
        stmt = select(OrganismModel).where(OrganismModel.parent_id == parent_id).order_by(
            OrganismModel.scientific_name
        )
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_by_name(self, name: str) -> list[Organism]:
        stmt = (
            select(OrganismModel)
            .join(OrganismNameModel, OrganismNameModel.organism_id == OrganismModel.id)
            .where(OrganismNameModel.name.ilike(f"%{name}%"))
            .distinct()
            .limit(50)
        )
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_all(
        self, *, cursor_id: uuid.UUID | None = None, limit: int | None = None
    ) -> list[Organism]:
        stmt = select(OrganismModel).order_by(OrganismModel.id)
        if cursor_id is not None:
            stmt = stmt.where(OrganismModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]
