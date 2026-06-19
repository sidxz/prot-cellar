"""Protein Catalog FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.protein_catalog.create_gene import CreateGene
from protcellar.application.protein_catalog.get_gene import GetGene
from protcellar.application.protein_catalog.list_genes import ListGenes
from protcellar.application.protein_catalog.update_gene import UpdateGene

from ._core import _get_use_case

__all__ = [
    "CreateGeneDep",
    "GetGeneDep",
    "ListGenesDep",
    "UpdateGeneDep",
]

# --- FastAPI type-alias Deps ---
CreateGeneDep = Annotated[CreateGene, Depends(_get_use_case(CreateGene))]
UpdateGeneDep = Annotated[UpdateGene, Depends(_get_use_case(UpdateGene))]
GetGeneDep = Annotated[GetGene, Depends(_get_use_case(GetGene))]
ListGenesDep = Annotated[ListGenes, Depends(_get_use_case(ListGenes))]
