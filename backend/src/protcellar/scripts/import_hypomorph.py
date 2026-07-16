"""CLI: bulk-import Hypomorph records from a CSV/TSV file.

Resolves the organism (to match loci to genes), parses the file, and upserts one
``Hypomorph`` record per row (idempotent on gene+condition+method).

Usage::

    uv run python -m protcellar.scripts.import_hypomorph --tax-id 83332 \\
        --file path/to/hypomorph.tsv

Requires ``DATABASE_URL`` in the environment (or ``.env``).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections import Counter
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.target_biology.bulk_upsert_hypomorph import (
    BulkUpsertHypomorph,
    BulkUpsertHypomorphCommand,
)
from protcellar.infrastructure.ingestion.hypomorph_csv import parse_hypomorph_csv
from protcellar.infrastructure.ingestion.organism_resolver import resolve_organism_id
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.hypomorph_repository import (
    SQLAlchemyHypomorphRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.scripts.import_proteome import _NoopDispatcher, _ServiceAuth

_DEFAULT_TAX_ID = 83332  # M. tuberculosis H37Rv


async def import_hypomorph(
    *,
    file: Path,
    tax_id: int = _DEFAULT_TAX_ID,
    organism_id: uuid.UUID | None = None,
    dry_run: bool = False,
) -> Counter[str]:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        resolved_id, gene_count = await resolve_organism_id(
            uow, organism_id=organism_id, tax_id=tax_id
        )
        if gene_count == 0:
            raise SystemExit(
                f"Organism {resolved_id} (tax {tax_id}) has 0 genes — import the proteome first."
            )
        records = parse_hypomorph_csv(file.read_text(encoding="utf-8"))
        command = BulkUpsertHypomorphCommand(
            organism_id=resolved_id, records=tuple(records), dry_run=dry_run
        )
        use_case = BulkUpsertHypomorph(
            uow,
            SQLAlchemyGeneRepository(uow),
            SQLAlchemyHypomorphRepository(uow),
            _NoopDispatcher(),
        )
        results = (await use_case(command, auth=_ServiceAuth())).unwrap()
        return Counter(r.status for r in results)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-import Hypomorph records from a file.")
    parser.add_argument("--file", type=Path, required=True, help="CSV/TSV file to import.")
    parser.add_argument("--tax-id", type=int, default=_DEFAULT_TAX_ID, help="NCBI taxon id.")
    parser.add_argument(
        "--organism-id", type=uuid.UUID, default=None, help="Explicit organism UUID."
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse + resolve, do not write.")
    args = parser.parse_args()
    counts = asyncio.run(
        import_hypomorph(
            file=args.file,
            tax_id=args.tax_id,
            organism_id=args.organism_id,
            dry_run=args.dry_run,
        )
    )
    print(
        f"created={counts['created']} updated={counts['updated']} "
        f"skipped={counts['skipped']} failed={counts['failed']}"
    )


if __name__ == "__main__":
    main()
