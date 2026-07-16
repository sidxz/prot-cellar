"""Target-biology FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.target_biology.crud_essentiality import (
    CreateEssentiality,
    DeleteEssentiality,
    UpdateEssentiality,
)
from protcellar.application.target_biology.get_gene_target_biology import GetGeneTargetBiology
from protcellar.application.target_biology.get_protein_target_biology import (
    GetProteinTargetBiology,
)

from ._core import _get_use_case

__all__ = [
    "CreateEssentialityDep",
    "DeleteEssentialityDep",
    "GetGeneTargetBiologyDep",
    "GetProteinTargetBiologyDep",
    "UpdateEssentialityDep",
]

GetGeneTargetBiologyDep = Annotated[
    GetGeneTargetBiology, Depends(_get_use_case(GetGeneTargetBiology))
]
GetProteinTargetBiologyDep = Annotated[
    GetProteinTargetBiology, Depends(_get_use_case(GetProteinTargetBiology))
]
CreateEssentialityDep = Annotated[CreateEssentiality, Depends(_get_use_case(CreateEssentiality))]
UpdateEssentialityDep = Annotated[UpdateEssentiality, Depends(_get_use_case(UpdateEssentiality))]
DeleteEssentialityDep = Annotated[DeleteEssentiality, Depends(_get_use_case(DeleteEssentiality))]
