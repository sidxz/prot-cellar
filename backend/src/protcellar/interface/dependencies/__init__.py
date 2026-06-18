"""Interface-layer dependency injection exports."""

from protcellar.interface.dependencies._core import (
    AuthDep,
    EventDispatcherDep,
    UoWDep,
    _get_use_case,
    get_auth,
    get_container,
    get_event_dispatcher,
    get_uow,
)
from protcellar.interface.dependencies._taxonomy import (
    CreateOrganismDep,
    CreateProteomeDep,
    CreateStrainDep,
    GetOrganismDep,
    GetProteomeDep,
    GetStrainDep,
    ListOrganismsDep,
    ListProteomesDep,
    ListStrainsDep,
    ResolveTaxIdDep,
    UpdateOrganismDep,
    UpdateStrainDep,
)
from protcellar.interface.dependencies._workspace_config import (
    CreateOrganizationDep,
    GetOrganizationDep,
    ListOrganizationsDep,
    UpdateOrganizationDep,
)

__all__ = [
    "AuthDep",
    "CreateOrganismDep",
    "CreateOrganizationDep",
    "CreateProteomeDep",
    "CreateStrainDep",
    "EventDispatcherDep",
    "GetOrganismDep",
    "GetOrganizationDep",
    "GetProteomeDep",
    "GetStrainDep",
    "ListOrganismsDep",
    "ListOrganizationsDep",
    "ListProteomesDep",
    "ListStrainsDep",
    "ResolveTaxIdDep",
    "UoWDep",
    "UpdateOrganismDep",
    "UpdateOrganizationDep",
    "UpdateStrainDep",
    "_get_use_case",
    "get_auth",
    "get_container",
    "get_event_dispatcher",
    "get_uow",
]
