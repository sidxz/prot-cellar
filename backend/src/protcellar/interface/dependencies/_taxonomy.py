"""Taxonomy FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.taxonomy.create_organism import CreateOrganism
from protcellar.application.taxonomy.create_proteome import CreateProteome
from protcellar.application.taxonomy.create_strain import CreateStrain
from protcellar.application.taxonomy.get_organism import GetOrganism
from protcellar.application.taxonomy.get_proteome import GetProteome
from protcellar.application.taxonomy.get_strain import GetStrain
from protcellar.application.taxonomy.list_organisms import ListOrganisms
from protcellar.application.taxonomy.list_proteomes import ListProteomes
from protcellar.application.taxonomy.list_strains import ListStrains
from protcellar.application.taxonomy.resolve_tax_id import ResolveTaxId
from protcellar.application.taxonomy.update_organism import UpdateOrganism
from protcellar.application.taxonomy.update_strain import UpdateStrain

from ._core import _get_use_case

__all__ = [
    "CreateOrganismDep",
    "CreateProteomeDep",
    "CreateStrainDep",
    "GetOrganismDep",
    "GetProteomeDep",
    "GetStrainDep",
    "ListOrganismsDep",
    "ListProteomesDep",
    "ListStrainsDep",
    "ResolveTaxIdDep",
    "UpdateOrganismDep",
    "UpdateStrainDep",
]

# --- FastAPI type-alias Deps ---
CreateOrganismDep = Annotated[CreateOrganism, Depends(_get_use_case(CreateOrganism))]
UpdateOrganismDep = Annotated[UpdateOrganism, Depends(_get_use_case(UpdateOrganism))]
GetOrganismDep = Annotated[GetOrganism, Depends(_get_use_case(GetOrganism))]
ListOrganismsDep = Annotated[ListOrganisms, Depends(_get_use_case(ListOrganisms))]
ResolveTaxIdDep = Annotated[ResolveTaxId, Depends(_get_use_case(ResolveTaxId))]
CreateStrainDep = Annotated[CreateStrain, Depends(_get_use_case(CreateStrain))]
UpdateStrainDep = Annotated[UpdateStrain, Depends(_get_use_case(UpdateStrain))]
GetStrainDep = Annotated[GetStrain, Depends(_get_use_case(GetStrain))]
ListStrainsDep = Annotated[ListStrains, Depends(_get_use_case(ListStrains))]
CreateProteomeDep = Annotated[CreateProteome, Depends(_get_use_case(CreateProteome))]
GetProteomeDep = Annotated[GetProteome, Depends(_get_use_case(GetProteome))]
ListProteomesDep = Annotated[ListProteomes, Depends(_get_use_case(ListProteomes))]
