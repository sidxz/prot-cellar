"""Protein Catalog FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.protein_catalog.bulk_upsert_proteins import BulkUpsertProteins
from protcellar.application.protein_catalog.create_gene import CreateGene
from protcellar.application.protein_catalog.create_protein import CreateProtein
from protcellar.application.protein_catalog.get_gene import GetGene
from protcellar.application.protein_catalog.get_protein import GetProtein
from protcellar.application.protein_catalog.list_genes import ListGenes
from protcellar.application.protein_catalog.list_proteins import ListProteins
from protcellar.application.protein_catalog.resolve_protein_id import ResolveProteinId
from protcellar.application.protein_catalog.update_gene import UpdateGene
from protcellar.application.protein_catalog.update_protein import UpdateProtein

from ._core import _get_use_case

__all__ = [
    "BulkUpsertProteinsDep",
    "CreateGeneDep",
    "CreateProteinDep",
    "GetGeneDep",
    "GetProteinDep",
    "ListGenesDep",
    "ListProteinsDep",
    "ResolveProteinIdDep",
    "UpdateGeneDep",
    "UpdateProteinDep",
]

# --- Protein Bulk ---
BulkUpsertProteinsDep = Annotated[BulkUpsertProteins, Depends(_get_use_case(BulkUpsertProteins))]

# --- Gene Deps ---
CreateGeneDep = Annotated[CreateGene, Depends(_get_use_case(CreateGene))]
UpdateGeneDep = Annotated[UpdateGene, Depends(_get_use_case(UpdateGene))]
GetGeneDep = Annotated[GetGene, Depends(_get_use_case(GetGene))]
ListGenesDep = Annotated[ListGenes, Depends(_get_use_case(ListGenes))]

# --- Protein Deps ---
CreateProteinDep = Annotated[CreateProtein, Depends(_get_use_case(CreateProtein))]
UpdateProteinDep = Annotated[UpdateProtein, Depends(_get_use_case(UpdateProtein))]
GetProteinDep = Annotated[GetProtein, Depends(_get_use_case(GetProtein))]
ListProteinsDep = Annotated[ListProteins, Depends(_get_use_case(ListProteins))]
ResolveProteinIdDep = Annotated[ResolveProteinId, Depends(_get_use_case(ResolveProteinId))]
