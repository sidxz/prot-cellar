"""Target-biology FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.target_biology.get_gene_target_biology import GetGeneTargetBiology
from protcellar.application.target_biology.get_protein_target_biology import (
    GetProteinTargetBiology,
)

from ._core import _get_use_case

__all__ = [
    "GetGeneTargetBiologyDep",
    "GetProteinTargetBiologyDep",
]

GetGeneTargetBiologyDep = Annotated[
    GetGeneTargetBiology, Depends(_get_use_case(GetGeneTargetBiology))
]
GetProteinTargetBiologyDep = Annotated[
    GetProteinTargetBiology, Depends(_get_use_case(GetProteinTargetBiology))
]
