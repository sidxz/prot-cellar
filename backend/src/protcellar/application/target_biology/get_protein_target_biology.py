"""GetProteinTargetBiology query — all protein-side target-biology records for a protein.

Gathers the three protein-attached typed records (protein production, protein
activity assay, unpublished structure) into one bundle for the protein detail
page. An unknown protein yields an empty bundle (see the gene-side sibling).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.repository import (
    ProteinActivityAssayRepository,
    ProteinProductionRepository,
    UnpublishedStructureRepository,
)
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure


@dataclass(frozen=True, kw_only=True)
class ProteinTargetBiology:
    protein_production: list[ProteinProduction]
    protein_activity_assay: list[ProteinActivityAssay]
    unpublished_structure: list[UnpublishedStructure]


@dataclass(frozen=True, kw_only=True)
class GetProteinTargetBiologyQuery(Query):
    protein_id: uuid.UUID


class GetProteinTargetBiology:
    def __init__(
        self,
        uow: UnitOfWork,
        protein_production_repo: ProteinProductionRepository,
        protein_activity_assay_repo: ProteinActivityAssayRepository,
        unpublished_structure_repo: UnpublishedStructureRepository,
    ) -> None:
        self._uow = uow
        self._protein_production = protein_production_repo
        self._protein_activity_assay = protein_activity_assay_repo
        self._unpublished_structure = unpublished_structure_repo

    async def __call__(
        self, input: GetProteinTargetBiologyQuery, auth: AuthContext | None = None
    ) -> Result[ProteinTargetBiology, DomainError]:
        require_authenticated(auth)
        ws, pid = SHARED_WORKSPACE_ID, input.protein_id
        async with self._uow:
            return Success(
                ProteinTargetBiology(
                    protein_production=await self._protein_production.find_by_protein(ws, pid),
                    protein_activity_assay=await self._protein_activity_assay.find_by_protein(
                        ws, pid
                    ),
                    unpublished_structure=await self._unpublished_structure.find_by_protein(
                        ws, pid
                    ),
                )
            )
