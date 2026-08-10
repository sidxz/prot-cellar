"""SQLAlchemy repository for Strain aggregates."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from protcellar.domain.taxonomy.strain import Strain
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import (
    SQLAlchemyRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import StrainTagLinkModel
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_filter import tag_filter_subquery
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import (
    StrainModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import readable_by


class SQLAlchemyStrainRepository(SQLAlchemyRepository[Strain, StrainModel]):
    model_class = StrainModel

    def _to_domain(self, model: StrainModel) -> Strain:
        return Strain(
            id=model.id,
            workspace_id=model.workspace_id,
            species_organism_id=model.species_organism_id,
            ncbi_taxon_id=model.ncbi_taxon_id,
            name=model.name,
            isolate=model.isolate,
            biosample_acc=model.biosample_acc,
            assembly_acc=model.assembly_acc,
            culture_collection=model.culture_collection,
            host_organism_id=model.host_organism_id,
            metadata=model.strain_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Strain) -> StrainModel:
        return StrainModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            species_organism_id=aggregate.species_organism_id,
            ncbi_taxon_id=aggregate.ncbi_taxon_id,
            name=aggregate.name,
            isolate=aggregate.isolate,
            biosample_acc=aggregate.biosample_acc,
            assembly_acc=aggregate.assembly_acc,
            culture_collection=aggregate.culture_collection,
            host_organism_id=aggregate.host_organism_id,
            strain_metadata=aggregate.metadata,
            version=aggregate.version,
        )

    def _update_model(self, model: StrainModel, aggregate: Strain) -> None:
        model.species_organism_id = aggregate.species_organism_id
        model.ncbi_taxon_id = aggregate.ncbi_taxon_id
        model.name = aggregate.name
        model.isolate = aggregate.isolate
        model.biosample_acc = aggregate.biosample_acc
        model.assembly_acc = aggregate.assembly_acc
        model.culture_collection = aggregate.culture_collection
        model.host_organism_id = aggregate.host_organism_id
        model.strain_metadata = aggregate.metadata

    async def find_by_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        match_all: bool = False,
    ) -> list[Strain]:
        """Strains visible to a workspace: its own plus shared reference strains.

        Strains imported as reference data (e.g. from a UniProt proteome) live in
        ``SHARED_WORKSPACE_ID`` and are shared with every workspace, mirroring how
        organisms/proteins/genes are served. A workspace's own strains stay private.
        """
        stmt = select(StrainModel).where(readable_by(StrainModel, workspace_id))
        if tag_ids:
            stmt = stmt.where(
                StrainModel.id.in_(
                    tag_filter_subquery(
                        StrainTagLinkModel,
                        "strain_id",
                        tag_ids,
                        workspace_id=workspace_id,
                        match_all=match_all,
                    )
                )
            )
        if cursor_id is not None:
            stmt = stmt.where(StrainModel.id > cursor_id)
        stmt = stmt.order_by(StrainModel.id)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]

    # find_readable / find_owned come from SQLAlchemyRepository — a strain lookup
    # by id needs no override, unlike find_by_workspace/find_by_species which
    # filter on columns other than the primary key.

    async def find_names_by_ids(
        self, ids: list[uuid.UUID], *, workspace_id: uuid.UUID
    ) -> dict[uuid.UUID, str]:
        """Batch id->name, scoped to what the workspace may read. Mirrors
        ``SQLAlchemyOrganismRepository.find_names_by_ids`` — see its docstring."""
        if not ids:
            return {}
        stmt = select(StrainModel.id, StrainModel.name).where(
            StrainModel.id.in_(ids), readable_by(StrainModel, workspace_id)
        )
        return {row.id: row.name for row in (await self._session.execute(stmt))}

    async def find_by_species(
        self, workspace_id: uuid.UUID, species_organism_id: uuid.UUID
    ) -> list[Strain]:
        stmt = (
            select(StrainModel)
            .where(
                StrainModel.workspace_id == workspace_id,
                StrainModel.species_organism_id == species_organism_id,
            )
            .order_by(StrainModel.id)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain_tracked(m) for m in result.scalars()]
