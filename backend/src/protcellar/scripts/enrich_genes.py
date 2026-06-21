"""CLI: enrich existing genes with genomic location + functional category.

Fetches the Mycobrowser *M. tuberculosis* H37Rv GFF, matches each locus tag to
an already-imported gene (within the resolved organism), and idempotently sets
the genomic-location fields + merges a CONTEXT ``functional_category``
annotation. Optionally layers DeJesus 2017 essentiality from a local table.

Usage::

    # Location + functional category (the reliable primary deliverable):
    python -m protcellar.scripts.enrich_genes --tax-id 83332

    # Also include essentiality from a local DeJesus table:
    python -m protcellar.scripts.enrich_genes --tax-id 83332 \\
        --essentiality-file path/to/dejesus_2017.tsv

Requires ``DATABASE_URL`` in the environment (or ``.env``). Wires the real
``httpx`` client + database around the tested ``GeneEnrichmentRunner``; the
orchestration logic itself lives in
``infrastructure.ingestion.gene_enrichment_runner``.

Organism resolution: genes are anchored to the *species* organism (1773), but a
strain taxon (83332 = H37Rv) is the natural identifier. We resolve the organism
that actually carries genes — preferring the requested ``--tax-id``, falling
back to its parent species — so the import works regardless of which node the
genes hang off after taxonomy refactors.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.protein_catalog.bulk_enrich_genes import (
    BulkEnrichGenes,
    EnrichSummary,
)
from protcellar.infrastructure.ingestion.gene_enrichment_runner import (
    EssentialityLoader,
    GeneEnrichmentRunner,
)
from protcellar.infrastructure.ingestion.mycobrowser_client import (
    MYCOBROWSER_H37RV_GFF_URL,
    MycobrowserClient,
)
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.scripts.import_proteome import _NoopDispatcher, _ServiceAuth

_DEFAULT_TAX_ID = 83332  # M. tuberculosis H37Rv


async def _resolve_organism_id(
    uow: AsyncUnitOfWork,
    *,
    organism_id: uuid.UUID | None,
    tax_id: int,
) -> tuple[uuid.UUID, int]:
    """Return ``(organism_id, gene_count)`` for the organism to enrich.

    An explicit ``--organism-id`` wins. Otherwise resolve by NCBI tax id and,
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
        org = await org_repo.find_by_tax_id(tax_id)
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


def _essentiality_loader(path: Path | None) -> EssentialityLoader | None:
    """Build a coroutine that reads the essentiality table, or ``None`` to skip."""
    if path is None:
        return None

    async def _load() -> str:
        return path.read_text(encoding="utf-8")

    return _load


async def enrich_genes(
    *,
    tax_id: int = _DEFAULT_TAX_ID,
    organism_id: uuid.UUID | None = None,
    gff_url: str = MYCOBROWSER_H37RV_GFF_URL,
    essentiality_file: Path | None = None,
) -> tuple[uuid.UUID, int, EnrichSummary]:
    """Resolve the organism, run the enrichment, and return the summary."""
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        resolved_id, gene_count = await _resolve_organism_id(
            uow, organism_id=organism_id, tax_id=tax_id
        )
        if gene_count == 0:
            raise SystemExit(
                f"Organism {resolved_id} (tax {tax_id}) has 0 genes — import the "
                "proteome first (python -m protcellar.scripts.import_proteome ...)."
            )
        gene_repo = SQLAlchemyGeneRepository(uow)
        bulk = BulkEnrichGenes(uow, gene_repo, _NoopDispatcher())
        async with httpx.AsyncClient() as http:
            client = MycobrowserClient(http)
            runner = GeneEnrichmentRunner(
                bulk,
                client,
                gff_url=gff_url,
                essentiality_loader=_essentiality_loader(essentiality_file),
            )
            summary = await runner.run(resolved_id, auth=_ServiceAuth())
        return resolved_id, gene_count, summary
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich genes with genomic location + functional category (Mycobrowser GFF)."
    )
    parser.add_argument(
        "--tax-id",
        type=int,
        default=_DEFAULT_TAX_ID,
        help="NCBI taxon id to resolve the organism (default 83332 = H37Rv).",
    )
    parser.add_argument(
        "--organism-id",
        type=uuid.UUID,
        default=None,
        help="Explicit organism UUID (overrides --tax-id resolution).",
    )
    parser.add_argument(
        "--gff-url",
        default=MYCOBROWSER_H37RV_GFF_URL,
        help="GFF URL to fetch (default: Mycobrowser H37Rv release 5).",
    )
    parser.add_argument(
        "--essentiality-file",
        type=Path,
        default=None,
        help="Optional local DeJesus 2017 essentiality table (TSV/CSV); skipped if absent.",
    )
    args = parser.parse_args()
    resolved_id, gene_count, summary = asyncio.run(
        enrich_genes(
            tax_id=args.tax_id,
            organism_id=args.organism_id,
            gff_url=args.gff_url,
            essentiality_file=args.essentiality_file,
        )
    )
    print(
        f"organism={resolved_id} genes={gene_count} "
        f"matched={summary.matched} unmatched={summary.unmatched} "
        f"locations_set={summary.locations_set} "
        f"annotations_written={summary.annotations_written}"
    )
    if summary.unmatched_loci:
        preview = ", ".join(summary.unmatched_loci[:10])
        more = (
            "" if len(summary.unmatched_loci) <= 10 else f" (+{len(summary.unmatched_loci) - 10})"
        )
        print(f"unmatched_loci[:10]: {preview}{more}")


if __name__ == "__main__":
    main()
