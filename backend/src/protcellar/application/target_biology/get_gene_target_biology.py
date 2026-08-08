"""GetGeneTargetBiology query — all gene-side target-biology records for a gene.

Gathers the five gene-attached typed records (essentiality, vulnerability,
hypomorph, CRISPRi strain, resistance mutation) into one bundle so the gene
detail page fetches them in a single request. An unknown gene simply yields an
empty bundle — this is a sub-collection read, and the detail page has already
resolved the gene itself.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.repository import (
    CrispriStrainRepository,
    EssentialityRepository,
    HypomorphRepository,
    ResistanceMutationRepository,
    VulnerabilityRepository,
)
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.vulnerability import Vulnerability


@dataclass(frozen=True, kw_only=True)
class GeneTargetBiology:
    essentiality: list[Essentiality]
    vulnerability: list[Vulnerability]
    hypomorph: list[Hypomorph]
    crispri_strain: list[CrispriStrain]
    resistance_mutation: list[ResistanceMutation]


@dataclass(frozen=True, kw_only=True)
class GetGeneTargetBiologyQuery(Query):
    gene_id: uuid.UUID


class GetGeneTargetBiology:
    def __init__(
        self,
        uow: UnitOfWork,
        essentiality_repo: EssentialityRepository,
        vulnerability_repo: VulnerabilityRepository,
        hypomorph_repo: HypomorphRepository,
        crispri_strain_repo: CrispriStrainRepository,
        resistance_mutation_repo: ResistanceMutationRepository,
    ) -> None:
        self._uow = uow
        self._essentiality = essentiality_repo
        self._vulnerability = vulnerability_repo
        self._hypomorph = hypomorph_repo
        self._crispri_strain = crispri_strain_repo
        self._resistance_mutation = resistance_mutation_repo

    async def __call__(
        self, input: GetGeneTargetBiologyQuery, auth: AuthContext | None = None
    ) -> Result[GeneTargetBiology, DomainError]:
        require_authenticated(auth)
        ws, gid = auth.workspace_id, input.gene_id  # type: ignore[union-attr]
        async with self._uow:
            return Success(
                GeneTargetBiology(
                    essentiality=await self._essentiality.find_by_gene(ws, gid),
                    vulnerability=await self._vulnerability.find_by_gene(ws, gid),
                    hypomorph=await self._hypomorph.find_by_gene(ws, gid),
                    crispri_strain=await self._crispri_strain.find_by_gene(ws, gid),
                    resistance_mutation=await self._resistance_mutation.find_by_gene(ws, gid),
                )
            )
