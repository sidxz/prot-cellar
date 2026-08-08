"""Cross-entity tag-browse read repository.

Given a set of tags, returns the entities of every taggable type that carry
them, each with a display label. A UNION ALL across the six link tables, each
branch joined to its entity table for the label. Read-only; not an aggregate.

Two visibility rules, both adaptations from chem-cellar (see
tag_link_repository.py for the fuller rationale):

- Entity visibility is global-or-mine: a shared reference entity (protein,
  gene, organism, strain, proteome) pinned to ``SHARED_WORKSPACE_ID`` is
  visible from every workspace's browse, not just GLOBAL itself. chem-cellar
  uses a strict ``== workspace_id`` because every taggable entity there is
  workspace-owned; a strict equality here would silently drop every global
  entity from the result.
- Tags themselves are always workspace-scoped: a link is only surfaced if its
  ``tag_id`` actually belongs to the caller's ``workspace_id`` (defense in
  depth against a foreign tag_id slipping through from a caller, mirroring the
  ``_owned`` check in ``SQLAlchemyTagLinkRepository.repoint``).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, distinct, func, literal, select, union_all
from sqlalchemy.sql import Select

from protcellar.application.workspace_config.tagging.list_tag_entities import TaggedEntityRow
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import (
    GeneModel,
    ProteinModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import (
    GeneTagLinkModel,
    OrganismTagLinkModel,
    ProteinTagLinkModel,
    ProteomeTagLinkModel,
    StrainTagLinkModel,
    TagModel,
    TargetTagLinkModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import (
    OrganismModel,
    ProteomeModel,
    StrainModel,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


class SQLAlchemyTagBrowseRepository:
    """Implements the application-layer ``TagBrowseReader`` protocol."""

    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self):  # AsyncSession
        return self._uow.session

    def _branch(
        self,
        entity_type: str,
        link_model: type,
        entity_id_attr: str,
        entity_model: type,
        label_col: ColumnElement[str],
        tag_ids: list[uuid.UUID],
        workspace_id: uuid.UUID,
        *,
        match_all: bool,
        extra_where: ColumnElement[bool] | None = None,
    ) -> Select[Any]:
        link_fk = getattr(link_model, entity_id_attr)
        # GROUP BY the entity PK so an entity tagged with several of the
        # selected tags collapses to one row; max(assigned_at) is the most
        # recent matching assignment. `match_all` keeps only entities carrying
        # every selected tag.
        stmt = (
            select(
                literal(entity_type).label("entity_type"),
                entity_model.id.label("entity_id"),
                label_col.label("label"),
                func.max(link_model.assigned_at).label("assigned_at"),
            )
            .join(link_model, link_fk == entity_model.id)
            .join(TagModel, TagModel.id == link_model.tag_id)
            .where(
                link_model.tag_id.in_(tag_ids),
                entity_model.workspace_id.in_([workspace_id, SHARED_WORKSPACE_ID]),
                TagModel.workspace_id == workspace_id,
            )
            .group_by(entity_model.id)
        )
        if extra_where is not None:
            stmt = stmt.where(extra_where)
        if match_all:
            stmt = stmt.having(func.count(distinct(link_model.tag_id)) == len(tag_ids))
        return stmt

    async def find_entities_for_tags(
        self,
        workspace_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        *,
        match_all: bool = False,
        types: list[str] | None = None,
        limit: int = 200,
    ) -> list[TaggedEntityRow]:
        if not tag_ids:
            return []
        ids = list(dict.fromkeys(tag_ids))  # dedup, preserve order
        b = self._branch
        branches = {
            "Protein": b(
                "Protein",
                ProteinTagLinkModel,
                "protein_id",
                ProteinModel,
                ProteinModel.primary_accession,
                ids,
                workspace_id,
                match_all=match_all,
            ),
            "Gene": b(
                "Gene",
                GeneTagLinkModel,
                "gene_id",
                GeneModel,
                GeneModel.primary_name,
                ids,
                workspace_id,
                match_all=match_all,
            ),
            "Target": b(
                "Target",
                TargetTagLinkModel,
                "target_id",
                TargetModel,
                TargetModel.pref_name,
                ids,
                workspace_id,
                match_all=match_all,
            ),
            "Organism": b(
                "Organism",
                OrganismTagLinkModel,
                "organism_id",
                OrganismModel,
                OrganismModel.scientific_name,
                ids,
                workspace_id,
                match_all=match_all,
                # Same tombstone guard as OrganismTagLinkRepository (Task 5): a
                # merged or soft-deleted organism should not resurface here even
                # though old links to it may still exist.
                extra_where=(
                    OrganismModel.merged_into_id.is_(None) & OrganismModel.is_deleted.is_(False)
                ),
            ),
            "Strain": b(
                "Strain",
                StrainTagLinkModel,
                "strain_id",
                StrainModel,
                StrainModel.name,
                ids,
                workspace_id,
                match_all=match_all,
            ),
            "Proteome": b(
                "Proteome",
                ProteomeTagLinkModel,
                "proteome_id",
                ProteomeModel,
                ProteomeModel.uniprot_proteome_id,
                ids,
                workspace_id,
                match_all=match_all,
            ),
        }
        selected = [s for name, s in branches.items() if not types or name in types]
        if not selected:
            return []
        unioned = union_all(*selected).subquery()
        stmt = (
            select(
                unioned.c.entity_type,
                unioned.c.entity_id,
                unioned.c.label,
                unioned.c.assigned_at,
            )
            .order_by(unioned.c.assigned_at.desc(), unioned.c.entity_type, unioned.c.label)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            TaggedEntityRow(
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                label=r.label,
                assigned_at=r.assigned_at,
            )
            for r in result.all()
        ]
