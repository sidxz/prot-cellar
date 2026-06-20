"""CLI: import a full UniProt proteome into the catalog.

Usage::

    python -m protcellar.scripts.import_proteome UP000001584 [--dry-run] [--limit N]

Requires ``DATABASE_URL`` in the environment (or ``.env``). Wires the real
``httpx`` client + database around the tested ``ProteomeImportRunner``; the
orchestration logic itself lives in ``infrastructure.ingestion.import_runner``.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.protein_catalog.bulk_upsert_proteins import BulkUpsertProteins
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.infrastructure.ingestion.import_runner import ImportSummary, ProteomeImportRunner
from protcellar.infrastructure.ingestion.uniprot_client import UniProtClient
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

_UNIPROT_BASE_URL = "https://rest.uniprot.org"
_ROLE_HIERARCHY: dict[str, int] = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}


class _ServiceAuth:
    """Admin auth context for the import service (satisfies ``AuthContext``)."""

    workspace_role = "admin"

    @property
    def user_id(self) -> uuid.UUID:
        return GLOBAL_WORKSPACE_ID

    @property
    def workspace_id(self) -> uuid.UUID:
        return GLOBAL_WORKSPACE_ID

    @property
    def is_admin(self) -> bool:
        return True

    def has_role(self, minimum_role: str) -> bool:
        return _ROLE_HIERARCHY.get(self.workspace_role, -1) >= _ROLE_HIERARCHY.get(
            minimum_role, 99
        )


class _NoopDispatcher:
    async def dispatch_all(self, events: object) -> None:
        return None


async def import_proteome(
    proteome_id: str, *, dry_run: bool = False, limit: int | None = None, force: bool = False
) -> ImportSummary:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        async with httpx.AsyncClient(base_url=_UNIPROT_BASE_URL, timeout=120.0) as http:
            protein_repo = SQLAlchemyProteinRepository(uow)
            bulk = BulkUpsertProteins(uow, protein_repo, _NoopDispatcher())
            runner = ProteomeImportRunner(uow, UniProtClient(http), bulk)
            return await runner.run(
                proteome_id, dry_run=dry_run, limit=limit, force=force, auth=_ServiceAuth()
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a UniProt proteome into prot-cellar.",
    )
    parser.add_argument("proteome_id", help="UniProt proteome id, e.g. UP000001584")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch + map + report, but persist nothing"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Import only the first N entries (smoke test)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-import even if the release version is unchanged"
    )
    args = parser.parse_args()
    summary = asyncio.run(
        import_proteome(
            args.proteome_id, dry_run=args.dry_run, limit=args.limit, force=args.force
        )
    )
    print(
        f"[{summary.proteome_id}] entries={summary.entries} created={summary.created} "
        f"updated={summary.updated} skipped={summary.skipped} failed={summary.failed} "
        f"members_linked={summary.members_linked} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
