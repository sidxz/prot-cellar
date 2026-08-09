"""Shared CLI harness for protein-side target-biology bulk imports.

Each protein is resolved per-accession by the command (via ``find_by_accession``)
— proteins are too numerous to index in memory. This harness just parses the file
and runs the given ``BulkUpsert*`` use case.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.scripts.import_proteome import _NoopDispatcher, _ServiceAuth


async def run_protein_import(
    *,
    file: Path,
    parse: Callable[[str], Sequence[Any]],
    command_cls: Any,
    use_case_cls: Any,
    record_repo_cls: Any,
    dry_run: bool = False,
) -> Counter[str]:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        records = parse(file.read_text(encoding="utf-8"))
        command = command_cls(
            target_workspace_id=SHARED_WORKSPACE_ID, records=tuple(records), dry_run=dry_run
        )
        use_case = use_case_cls(
            uow, SQLAlchemyProteinRepository(uow), record_repo_cls(uow), _NoopDispatcher()
        )
        results = (await use_case(command, auth=_ServiceAuth())).unwrap()
        return Counter(r.status for r in results)
    finally:
        await engine.dispose()


def protein_import_main(
    *,
    description: str,
    parse: Callable[[str], Sequence[Any]],
    command_cls: Any,
    use_case_cls: Any,
    record_repo_cls: Any,
) -> None:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--file", type=Path, required=True, help="CSV/TSV file to import.")
    parser.add_argument("--dry-run", action="store_true", help="Parse + resolve, do not write.")
    args = parser.parse_args()
    counts = asyncio.run(
        run_protein_import(
            file=args.file,
            parse=parse,
            command_cls=command_cls,
            use_case_cls=use_case_cls,
            record_repo_cls=record_repo_cls,
            dry_run=args.dry_run,
        )
    )
    print(
        f"created={counts['created']} updated={counts['updated']} "
        f"skipped={counts['skipped']} failed={counts['failed']}"
    )
