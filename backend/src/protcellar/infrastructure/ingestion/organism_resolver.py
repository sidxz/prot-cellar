"""Utility: resolve the organism UUID (and gene count) for enrichment runs.

Extracted from ``protcellar.scripts.enrich_genes`` so that both the CLI script
and the infrastructure adapter wiring layer can import it without creating an
infrastructure→scripts reverse dependency.
"""

from __future__ import annotations

import uuid

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


async def resolve_organism_id(
    uow: AsyncUnitOfWork,
    *,
    organism_id: uuid.UUID | None,
    tax_id: int,
) -> tuple[uuid.UUID, int]:
    """Return ``(organism_id, gene_count)`` for the organism to enrich.

    An explicit ``organism_id`` wins.  Otherwise resolve by NCBI tax id and,
    if that node has no genes (e.g. the strain taxon after genes were repointed
    to the species), walk up to its parent — picking the first organism that
    actually carries genes.
    """
    async with uow:
        gene_repo = SQLAlchemyGeneRepository(uow)
        if organism_id is not None:
            count = len(await gene_repo.list_by_organism(organism_id))
            return organism_id, count

        org_repo = SQLAlchemyOrganismRepository(uow)
        org = await org_repo.find_by_tax_id(tax_id, workspace_id=SHARED_WORKSPACE_ID)
        if org is None:
            raise SystemExit(f"No organism found for NCBI tax id {tax_id}.")

        # Candidate chain: the resolved node, then its ancestors (species, ...).
        candidates: list[uuid.UUID] = [org.id]
        seen = {org.id}
        cursor = org
        while cursor.parent_id is not None and cursor.parent_id not in seen:
            parent = await org_repo.find_by_id(cursor.parent_id)
            if parent is None:
                break
            candidates.append(parent.id)
            seen.add(parent.id)
            cursor = parent

        best: tuple[uuid.UUID, int] | None = None
        for cand in candidates:
            count = len(await gene_repo.list_by_organism(cand))
            if count > 0:
                return cand, count
            if best is None:
                best = (cand, count)
        # No ancestor had genes — return the originally-resolved node (count 0).
        assert best is not None
        return best
