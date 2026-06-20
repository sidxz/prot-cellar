"""SQLAlchemy Proteome repository."""

from __future__ import annotations

import uuid

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.domain.taxonomy.repository import ProteomeRepository
from protcellar.infrastructure.persistence.sqlalchemy.base_repository import SQLAlchemyRepository
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import ProteinModel
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import (
    ProteomeModel,
    ProteomeProteinModel,
)


class SQLAlchemyProteomeRepository(
    SQLAlchemyRepository[Proteome, ProteomeModel], ProteomeRepository
):
    model_class = ProteomeModel

    def _to_domain(self, model: ProteomeModel) -> Proteome:
        return Proteome(
            id=model.id,
            uniprot_proteome_id=model.uniprot_proteome_id,
            organism_id=model.organism_id,
            strain_id=model.strain_id,
            proteome_type=ProteomeType(model.proteome_type),
            is_reference=model.is_reference,
            assembly_acc=model.assembly_acc,
            source_version=model.source_version,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, aggregate: Proteome) -> ProteomeModel:
        return ProteomeModel(
            id=aggregate.id,
            workspace_id=aggregate.workspace_id,
            uniprot_proteome_id=aggregate.uniprot_proteome_id,
            organism_id=aggregate.organism_id,
            strain_id=aggregate.strain_id,
            proteome_type=aggregate.proteome_type.value,
            is_reference=aggregate.is_reference,
            assembly_acc=aggregate.assembly_acc,
            source_version=aggregate.source_version,
            version=aggregate.version,
        )

    def _update_model(self, model: ProteomeModel, aggregate: Proteome) -> None:
        model.uniprot_proteome_id = aggregate.uniprot_proteome_id
        model.organism_id = aggregate.organism_id
        model.strain_id = aggregate.strain_id
        model.proteome_type = aggregate.proteome_type.value
        model.is_reference = aggregate.is_reference
        model.assembly_acc = aggregate.assembly_acc
        model.source_version = aggregate.source_version

    async def find_by_proteome_id(self, uniprot_proteome_id: str) -> Proteome | None:
        stmt = select(ProteomeModel).where(
            ProteomeModel.uniprot_proteome_id == uniprot_proteome_id
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_domain_tracked(model) if model else None

    async def find_by_organism(self, organism_id: uuid.UUID) -> list[Proteome]:
        stmt = (
            select(ProteomeModel)
            .where(ProteomeModel.organism_id == organism_id)
            .order_by(ProteomeModel.id)
        )
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[Proteome]:
        stmt = select(ProteomeModel).order_by(ProteomeModel.id)
        if cursor_id is not None:
            stmt = stmt.where(ProteomeModel.id > cursor_id)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [self._to_domain_tracked(m) for m in (await self._session.execute(stmt)).scalars()]

    async def add_protein(self, proteome_id: uuid.UUID, protein_id: uuid.UUID) -> None:
        """Link a protein to a proteome (idempotent on the (proteome, protein) pair)."""
        existing = await self._session.execute(
            select(ProteomeProteinModel.id).where(
                ProteomeProteinModel.proteome_id == proteome_id,
                ProteomeProteinModel.protein_id == protein_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return
        self._session.add(ProteomeProteinModel(proteome_id=proteome_id, protein_id=protein_id))

    async def list_protein_ids(self, proteome_id: uuid.UUID) -> list[uuid.UUID]:
        """Return the ids of all proteins that belong to the given proteome."""
        stmt = (
            select(ProteomeProteinModel.protein_id)
            .where(ProteomeProteinModel.proteome_id == proteome_id)
            .order_by(ProteomeProteinModel.protein_id)
        )
        rows = await self._session.execute(stmt)
        return [row[0] for row in rows.all()]

    async def remove_protein(self, proteome_id: uuid.UUID, protein_id: uuid.UUID) -> None:
        await self._session.execute(
            sa_delete(ProteomeProteinModel).where(
                ProteomeProteinModel.proteome_id == proteome_id,
                ProteomeProteinModel.protein_id == protein_id,
            )
        )

    async def list_members(self, proteome_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
        stmt = (
            select(ProteomeProteinModel.protein_id, ProteinModel.primary_accession)
            .join(ProteinModel, ProteinModel.id == ProteomeProteinModel.protein_id)
            .where(ProteomeProteinModel.proteome_id == proteome_id)
        )
        return [(r[0], r[1]) for r in (await self._session.execute(stmt)).all()]
