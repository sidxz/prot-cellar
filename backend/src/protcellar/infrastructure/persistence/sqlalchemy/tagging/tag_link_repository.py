"""Lightweight (non-aggregate) repositories for tag↔entity links.

One generic base, six type-bound subclasses, and a factory. Mirrors
chem-cellar's tag_link_repository.py: direct SQL, on_conflict_do_nothing,
workspace defense via a lookup against the entity table.

Adaptation from chem-cellar (deliberate, not a port bug): in chem-cellar every
taggable entity is workspace-owned, so ``entity_exists_in_workspace`` checks
``entity.workspace_id == workspace_id`` (strict). In prot-cellar, reference
entities (proteins/genes/organisms/strains/proteomes) are shared, pinned to
``GLOBAL_WORKSPACE_ID`` (mirroring ``SQLAlchemyStrainRepository`` /
``StrainModel.workspace_id.in_([workspace_id, GLOBAL_WORKSPACE_ID])``), while
Target is per-workspace — but tags are always workspace-scoped, so a workspace
must be able to tag both its own entities AND the shared global ones. The
check is therefore "global-or-mine": ``entity.workspace_id IN (workspace_id,
GLOBAL_WORKSPACE_ID)``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.workspace_config.tagging.tag import (
    AssignedTag,
    Tag,
    TaggableEntityType,
    TagName,
)
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


def _tag_model_to_domain(model: TagModel) -> Tag:
    # ponytail: duplicates SQLAlchemyTagRepository._to_domain (Task 4, already
    # committed + tested). chem-cellar hoists an identical `tag_model_to_domain`
    # module function shared by both files; this task's commit is scoped to the
    # two new tagging files, so the 8-line mapping is repeated here rather than
    # touching tag_repository.py. Promote to a shared function if a third
    # caller needs it.
    return Tag(
        id=model.id,
        workspace_id=model.workspace_id,
        name=TagName(key=model.key, value=model.value),
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
        version=model.version,
    )


class SQLAlchemyTagLinkRepository:
    """Base for a single link table. Subclasses set the three class attributes."""

    link_model: type
    entity_model: type
    entity_id_attr: str

    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self):
        return self._uow.session

    @property
    def _entity_col(self):
        return getattr(self.link_model, self.entity_id_attr)

    async def entity_exists_in_workspace(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID
    ) -> bool:
        """Global-or-mine: visible if owned by ``workspace_id`` OR pinned to
        ``GLOBAL_WORKSPACE_ID`` (shared reference data)."""
        stmt = select(self.entity_model.id).where(
            self.entity_model.id == entity_id,
            self.entity_model.workspace_id.in_([workspace_id, GLOBAL_WORKSPACE_ID]),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(
        self,
        workspace_id: uuid.UUID,
        entity_id: uuid.UUID,
        tag_id: uuid.UUID,
        assigned_by: uuid.UUID,
    ) -> bool:
        """Link ``tag_id`` to the entity. Returns ``True`` iff a new row was
        inserted (``False`` when the entity is absent or the link already
        existed) so callers can avoid emitting a spurious assignment event."""
        if not await self.entity_exists_in_workspace(workspace_id, entity_id):
            return False
        stmt = (
            pg_insert(self.link_model)
            .values(
                **{self.entity_id_attr: entity_id},
                tag_id=tag_id,
                assigned_by=assigned_by,
            )
            .on_conflict_do_nothing()
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def remove(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        if not await self.entity_exists_in_workspace(workspace_id, entity_id):
            return
        stmt = delete(self.link_model).where(
            self._entity_col == entity_id, self.link_model.tag_id == tag_id
        )
        await self._session.execute(stmt)

    async def set_for_entity(
        self,
        workspace_id: uuid.UUID,
        entity_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        assigned_by: uuid.UUID,
    ) -> None:
        if not await self.entity_exists_in_workspace(workspace_id, entity_id):
            return
        # Reference entities (proteins/genes/organisms/...) are tagged by many
        # workspaces against the same shared row, so the reconcile-DELETE must
        # only ever touch tag links this workspace owns — otherwise workspace
        # A reconciling its own tags collaterally deletes workspace B's links
        # on the same entity (cross-tenant data loss).
        owned = select(TagModel.id).where(TagModel.workspace_id == workspace_id)
        del_stmt = delete(self.link_model).where(
            self._entity_col == entity_id, self.link_model.tag_id.in_(owned)
        )
        if tag_ids:
            del_stmt = del_stmt.where(self.link_model.tag_id.not_in(tag_ids))
        await self._session.execute(del_stmt)
        for tag_id in tag_ids:
            stmt = (
                pg_insert(self.link_model)
                .values(
                    **{self.entity_id_attr: entity_id},
                    tag_id=tag_id,
                    assigned_by=assigned_by,
                )
                .on_conflict_do_nothing()
            )
            await self._session.execute(stmt)

    async def find_tags_for_entity(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID
    ) -> list[Tag]:
        stmt = (
            select(TagModel)
            .join(self.link_model, TagModel.id == self.link_model.tag_id)
            .where(self._entity_col == entity_id, TagModel.workspace_id == workspace_id)
            .order_by(TagModel.normalized_key, TagModel.normalized_value)
        )
        result = await self._session.execute(stmt)
        return [_tag_model_to_domain(m) for m in result.scalars()]

    async def find_assigned_tags_for_entity(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID
    ) -> list[AssignedTag]:
        stmt = (
            select(TagModel, self.link_model.assigned_by, self.link_model.assigned_at)
            .join(self.link_model, TagModel.id == self.link_model.tag_id)
            .where(self._entity_col == entity_id, TagModel.workspace_id == workspace_id)
            .order_by(TagModel.normalized_key, TagModel.normalized_value)
        )
        result = await self._session.execute(stmt)
        return [
            AssignedTag(
                tag=_tag_model_to_domain(model),
                assigned_by=assigned_by,
                assigned_at=assigned_at,
            )
            for model, assigned_by, assigned_at in result.all()
        ]

    async def repoint(
        self, workspace_id: uuid.UUID, from_tag_id: uuid.UUID, to_tag_id: uuid.UUID
    ) -> None:
        """Move every link from ``from_tag_id`` to ``to_tag_id`` (merge).

        Copies the source links onto the target tag (skipping rows where the
        entity already carries the target — composite-PK conflict), then deletes
        the source links. Both statements verify that both tags belong to
        ``workspace_id`` (defence-in-depth — link tables carry no workspace
        column), so a cross-workspace call is a no-op rather than a leak or
        a delete-without-merge.
        """

        def _owned(tag_id: uuid.UUID):
            return select(TagModel.id).where(
                TagModel.id == tag_id, TagModel.workspace_id == workspace_id
            )

        col = self._entity_col
        src = select(
            col,
            literal(to_tag_id),
            self.link_model.assigned_by,
            self.link_model.assigned_at,
        ).where(
            self.link_model.tag_id.in_(_owned(from_tag_id)),
            _owned(to_tag_id).exists(),
        )
        ins = (
            pg_insert(self.link_model)
            .from_select([self.entity_id_attr, "tag_id", "assigned_by", "assigned_at"], src)
            .on_conflict_do_nothing()
        )
        await self._session.execute(ins)
        await self._session.execute(
            delete(self.link_model).where(
                self.link_model.tag_id.in_(_owned(from_tag_id)),
                _owned(to_tag_id).exists(),
            )
        )


class ProteinTagLinkRepository(SQLAlchemyTagLinkRepository):
    link_model = ProteinTagLinkModel
    entity_model = ProteinModel
    entity_id_attr = "protein_id"


class GeneTagLinkRepository(SQLAlchemyTagLinkRepository):
    link_model = GeneTagLinkModel
    entity_model = GeneModel
    entity_id_attr = "gene_id"


class TargetTagLinkRepository(SQLAlchemyTagLinkRepository):
    link_model = TargetTagLinkModel
    entity_model = TargetModel
    entity_id_attr = "target_id"


class OrganismTagLinkRepository(SQLAlchemyTagLinkRepository):
    link_model = OrganismTagLinkModel
    entity_model = OrganismModel
    entity_id_attr = "organism_id"

    async def entity_exists_in_workspace(
        self, workspace_id: uuid.UUID, entity_id: uuid.UUID
    ) -> bool:
        """Same global-or-mine visibility, plus: a tombstoned organism is not a
        valid tag target — its links would be invisible in normal views and
        lost on the next merge. Mirrors chem-cellar's molecule tombstone guard
        (``merged_into_id IS NULL``); also excludes soft-deleted rows
        (``is_deleted``), the other tombstone flag on ``OrganismModel``. No
        other taggable entity model here carries a merge/soft-delete column."""
        stmt = select(OrganismModel.id).where(
            OrganismModel.id == entity_id,
            OrganismModel.workspace_id.in_([workspace_id, GLOBAL_WORKSPACE_ID]),
            OrganismModel.merged_into_id.is_(None),
            OrganismModel.is_deleted.is_(False),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


class StrainTagLinkRepository(SQLAlchemyTagLinkRepository):
    link_model = StrainTagLinkModel
    entity_model = StrainModel
    entity_id_attr = "strain_id"


class ProteomeTagLinkRepository(SQLAlchemyTagLinkRepository):
    link_model = ProteomeTagLinkModel
    entity_model = ProteomeModel
    entity_id_attr = "proteome_id"


_REGISTRY: dict[TaggableEntityType, type[SQLAlchemyTagLinkRepository]] = {
    TaggableEntityType.PROTEIN: ProteinTagLinkRepository,
    TaggableEntityType.GENE: GeneTagLinkRepository,
    TaggableEntityType.TARGET: TargetTagLinkRepository,
    TaggableEntityType.ORGANISM: OrganismTagLinkRepository,
    TaggableEntityType.STRAIN: StrainTagLinkRepository,
    TaggableEntityType.PROTEOME: ProteomeTagLinkRepository,
}


def get_tag_link_repository(
    entity_type: TaggableEntityType, uow: AsyncUnitOfWork
) -> SQLAlchemyTagLinkRepository:
    """Factory: the link repository bound to ``entity_type``'s table."""
    return _REGISTRY[entity_type](uow)


class SQLAlchemyTagLinkRepositoryProvider:
    """Resolves the right link repository for an entity type, bound to a uow."""

    def __init__(self, uow: AsyncUnitOfWork) -> None:
        self._uow = uow

    def for_type(self, entity_type: TaggableEntityType) -> SQLAlchemyTagLinkRepository:
        return get_tag_link_repository(entity_type, self._uow)
