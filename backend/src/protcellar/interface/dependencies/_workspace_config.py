"""Workspace-config FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

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

from ._core import _get_use_case

__all__ = [
    "AssignTagDep",
    "CreateOrganizationDep",
    "DeleteTagDep",
    "GetOrganizationDep",
    "GetTagsForEntityDep",
    "ListOrganizationsDep",
    "ListTagEntitiesDep",
    "ListTagsDep",
    "MergeTagsDep",
    "RenameTagDep",
    "SetEntityTagsDep",
    "UnassignTagDep",
    "UpdateOrganizationDep",
]

# --- FastAPI type-alias Deps ---
CreateOrganizationDep = Annotated[CreateOrganization, Depends(_get_use_case(CreateOrganization))]
UpdateOrganizationDep = Annotated[UpdateOrganization, Depends(_get_use_case(UpdateOrganization))]
GetOrganizationDep = Annotated[GetOrganization, Depends(_get_use_case(GetOrganization))]
ListOrganizationsDep = Annotated[ListOrganizations, Depends(_get_use_case(ListOrganizations))]

# --- Tagging ---
AssignTagDep = Annotated[AssignTag, Depends(_get_use_case(AssignTag))]
UnassignTagDep = Annotated[UnassignTag, Depends(_get_use_case(UnassignTag))]
SetEntityTagsDep = Annotated[SetEntityTags, Depends(_get_use_case(SetEntityTags))]
GetTagsForEntityDep = Annotated[GetTagsForEntity, Depends(_get_use_case(GetTagsForEntity))]
ListTagsDep = Annotated[ListTags, Depends(_get_use_case(ListTags))]
RenameTagDep = Annotated[RenameTag, Depends(_get_use_case(RenameTag))]
MergeTagsDep = Annotated[MergeTags, Depends(_get_use_case(MergeTags))]
DeleteTagDep = Annotated[DeleteTag, Depends(_get_use_case(DeleteTag))]
ListTagEntitiesDep = Annotated[ListTagEntities, Depends(_get_use_case(ListTagEntities))]
