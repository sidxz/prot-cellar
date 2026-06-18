"""Workspace-config FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.workspace_config.create_organization import CreateOrganization
from protcellar.application.workspace_config.get_organization import GetOrganization
from protcellar.application.workspace_config.list_organizations import ListOrganizations
from protcellar.application.workspace_config.update_organization import UpdateOrganization

from ._core import _get_use_case

__all__ = [
    "CreateOrganizationDep",
    "GetOrganizationDep",
    "ListOrganizationsDep",
    "UpdateOrganizationDep",
]

# --- FastAPI type-alias Deps ---
CreateOrganizationDep = Annotated[CreateOrganization, Depends(_get_use_case(CreateOrganization))]
UpdateOrganizationDep = Annotated[UpdateOrganization, Depends(_get_use_case(UpdateOrganization))]
GetOrganizationDep = Annotated[GetOrganization, Depends(_get_use_case(GetOrganization))]
ListOrganizationsDep = Annotated[ListOrganizations, Depends(_get_use_case(ListOrganizations))]
