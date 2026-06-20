"""CLI: import the GO ontology (go-basic.obo) into the gene_ontology context.

Usage::

    python -m protcellar.scripts.import_go_ontology [--force]

Requires ``DATABASE_URL`` in the environment. Downloads ~32 MB of OBO and upserts
~47k terms + ~80k edges; idempotent and version-gated on the GO release date.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.infrastructure.ingestion.go_import_runner import GoImportRunner, GoImportSummary
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


async def import_go_ontology(*, force: bool = False) -> GoImportSummary:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        return await GoImportRunner(uow).run(force=force)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the GO ontology into prot-cellar.")
    parser.add_argument(
        "--force", action="store_true", help="Re-import even if the GO release is unchanged"
    )
    args = parser.parse_args()
    summary = asyncio.run(import_go_ontology(force=args.force))
    print(
        f"GO {summary.source_version}: terms={summary.terms_upserted} "
        f"edges={summary.edges} skipped_unchanged={summary.skipped_unchanged}"
    )


if __name__ == "__main__":
    main()
