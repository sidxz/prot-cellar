"""GetGeneNeighborhood query — flanking genes on a gene's replicon.

Loads the anchor gene, requires it to carry a genomic location, fetches its
``window`` nearest neighbours on the same accession (the center gene included),
and projects each to a compact summary. The essentiality call is read from each
gene's target-biology ``Essentiality`` records (the plugin's home) rather than a
legacy gene annotation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.repository import EssentialityRepository

_ESS_SEVERITY = {
    EssentialityClass.ESSENTIAL: 4,
    EssentialityClass.GROWTH_DEFECT: 3,
    EssentialityClass.NON_ESSENTIAL: 2,
    EssentialityClass.GROWTH_ADVANTAGE: 1,
    EssentialityClass.UNCERTAIN: 0,
}


def _consensus_essentiality(records: list[Essentiality]) -> str | None:
    """Modal essentiality call across a gene's records, ties broken toward the more
    severe call — mirrors the frontend call-scale so a gene reads the same call in
    the neighborhood track and in its own Essentiality section."""
    if not records:
        return None
    counts: dict[EssentialityClass, int] = {}
    for r in records:
        counts[r.classification] = counts.get(r.classification, 0) + 1
    return str(max(counts, key=lambda c: (counts[c], _ESS_SEVERITY[c])))


@dataclass(frozen=True, kw_only=True)
class GeneNeighborSummary:
    id: uuid.UUID
    primary_name: str
    genomic_start: int | None
    genomic_end: int | None
    genomic_strand: str | None
    essentiality: str | None


@dataclass(frozen=True, kw_only=True)
class GeneNeighborhood:
    center_id: uuid.UUID
    accession: str
    neighbors: list[GeneNeighborSummary]


@dataclass(frozen=True, kw_only=True)
class GetGeneNeighborhoodQuery(Query):
    gene_id: uuid.UUID
    window: int = 8


class GetGeneNeighborhood:
    def __init__(
        self, uow: UnitOfWork, repo: GeneRepository, ess_repo: EssentialityRepository
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._ess_repo = ess_repo

    async def __call__(
        self, input: GetGeneNeighborhoodQuery, auth: AuthContext | None = None
    ) -> Result[GeneNeighborhood, DomainError]:
        require_authenticated(auth)
        async with self._uow:
            gene = await self._repo.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, input.gene_id)
            if gene is None:
                return Failure(NotFoundError("Gene", str(input.gene_id)))
            if gene.genomic_accession is None or gene.genomic_start is None:
                return Failure(NotFoundError("GeneNeighborhood", str(input.gene_id)))

            neighbors = await self._repo.find_genomic_neighbors(
                organism_id=gene.organism_id,
                genomic_accession=gene.genomic_accession,
                center_start=gene.genomic_start,
                window=input.window,
            )
            summaries: list[GeneNeighborSummary] = []
            for n in neighbors:
                # ponytail: one find_by_gene per neighbor (~2*window+1 lookups). Add a
                # batch find_by_genes to the repo if this view ever gets slow.
                records = await self._ess_repo.find_by_gene(GLOBAL_WORKSPACE_ID, n.id)
                summaries.append(
                    GeneNeighborSummary(
                        id=n.id,
                        primary_name=n.primary_name,
                        genomic_start=n.genomic_start,
                        genomic_end=n.genomic_end,
                        genomic_strand=n.genomic_strand,
                        essentiality=_consensus_essentiality(records),
                    )
                )
            return Success(
                GeneNeighborhood(
                    center_id=gene.id, accession=gene.genomic_accession, neighbors=summaries
                )
            )
