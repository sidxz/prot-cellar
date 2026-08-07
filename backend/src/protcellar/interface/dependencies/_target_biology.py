"""Target-biology FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.target_biology.crud import (
    CreateTargetBiologyRecord,
    DeleteTargetBiologyRecord,
    UpdateTargetBiologyRecord,
)
from protcellar.application.target_biology.get_gene_target_biology import GetGeneTargetBiology
from protcellar.application.target_biology.get_protein_target_biology import (
    GetProteinTargetBiology,
)
from protcellar.application.target_biology.suggested_values import SuggestedValuesReader

from ._core import _get_use_case

__all__ = [
    "CreateTargetBiologyRecordDep",
    "DeleteTargetBiologyRecordDep",
    "GetGeneTargetBiologyDep",
    "GetProteinTargetBiologyDep",
    "SuggestedValuesReaderDep",
    "UpdateTargetBiologyRecordDep",
]

GetGeneTargetBiologyDep = Annotated[
    GetGeneTargetBiology, Depends(_get_use_case(GetGeneTargetBiology))
]
GetProteinTargetBiologyDep = Annotated[
    GetProteinTargetBiology, Depends(_get_use_case(GetProteinTargetBiology))
]
CreateTargetBiologyRecordDep = Annotated[
    CreateTargetBiologyRecord, Depends(_get_use_case(CreateTargetBiologyRecord))
]
UpdateTargetBiologyRecordDep = Annotated[
    UpdateTargetBiologyRecord, Depends(_get_use_case(UpdateTargetBiologyRecord))
]
DeleteTargetBiologyRecordDep = Annotated[
    DeleteTargetBiologyRecord, Depends(_get_use_case(DeleteTargetBiologyRecord))
]
SuggestedValuesReaderDep = Annotated[
    SuggestedValuesReader, Depends(_get_use_case(SuggestedValuesReader))
]
