"""Workspace config DI bindings — registers Organization + tagging use cases into Lagom."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.workspace_config.create_organization import CreateOrganization
from protcellar.application.workspace_config.get_organization import GetOrganization
from protcellar.application.workspace_config.list_organizations import ListOrganizations
from protcellar.application.workspace_config.tagging.assign_tag import AssignTag
from protcellar.application.workspace_config.tagging.delete_tag import DeleteTag
from protcellar.application.workspace_config.tagging.get_tags_for_entity import GetTagsForEntity
from protcellar.application.workspace_config.tagging.list_tag_entities import ListTagEntities
from protcellar.application.workspace_config.tagging.list_tags import ListTags
from protcellar.application.workspace_config.tagging.merge_tags import MergeTags
from protcellar.application.workspace_config.tagging.rename_tag import RenameTag
from protcellar.application.workspace_config.tagging.set_entity_tags import SetEntityTags
from protcellar.application.workspace_config.tagging.unassign_tag import UnassignTag
from protcellar.application.workspace_config.update_organization import UpdateOrganization
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_browse_repository import (
    SQLAlchemyTagBrowseRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_link_repository import (
    SQLAlchemyTagLinkRepositoryProvider,
)
from protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository import (
    SQLAlchemyTagRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_config.organization_repository import (  # noqa: E501
    SQLAlchemyOrganizationRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_workspace_config(container: Container) -> None:
    """Register Organization + tagging use cases into the Lagom container."""

    # --- Organizations ---
    def _org_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyOrganizationRepository(uow), c[EventDispatcher])

        return _f

    def _org_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyOrganizationRepository(uow))

        return _f

    container.define(CreateOrganization, _org_cmd(CreateOrganization))
    container.define(UpdateOrganization, _org_cmd(UpdateOrganization))
    container.define(GetOrganization, _org_query(GetOrganization))
    container.define(ListOrganizations, _org_query(ListOrganizations))

    # --- Tagging ---
    # Commands needing tag_repo + link_provider + dispatcher: assign/unassign/set/merge.
    def _tag_link_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(
                uow,
                SQLAlchemyTagRepository(uow),
                SQLAlchemyTagLinkRepositoryProvider(uow),
                c[EventDispatcher],
            )

        return _f

    # Commands needing only tag_repo + dispatcher: rename/delete.
    def _tag_repo_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyTagRepository(uow), c[EventDispatcher])

        return _f

    container.define(AssignTag, _tag_link_cmd(AssignTag))
    container.define(UnassignTag, _tag_link_cmd(UnassignTag))
    container.define(SetEntityTags, _tag_link_cmd(SetEntityTags))
    container.define(MergeTags, _tag_link_cmd(MergeTags))
    container.define(RenameTag, _tag_repo_cmd(RenameTag))
    container.define(DeleteTag, _tag_repo_cmd(DeleteTag))

    # Queries: no dispatcher.
    def _get_tags_for_entity(c: Container) -> Any:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return GetTagsForEntity(uow, SQLAlchemyTagLinkRepositoryProvider(uow))

    def _list_tags(c: Container) -> Any:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return ListTags(uow, SQLAlchemyTagRepository(uow))

    def _list_tag_entities(c: Container) -> Any:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return ListTagEntities(uow, SQLAlchemyTagBrowseRepository(uow))

    container.define(GetTagsForEntity, _get_tags_for_entity)
    container.define(ListTags, _list_tags)
    container.define(ListTagEntities, _list_tag_entities)
