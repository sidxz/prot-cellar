"""CLI: export the full database as a portable archive for developer replication.

Dumps every domain table (UUIDs preserved verbatim) to JSONL inside a tar.gz,
plus a manifest recording the schema revision and which non-shared workspace
ids appear — ``import_data.py`` uses both to validate and remap on restore.

Usage:
    uv run python -m protcellar.scripts.export_data [-o protcellar-data.tar.gz]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import tarfile
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import Table, select, text
from sqlalchemy.ext.asyncio import create_async_engine

# The metadata module imports every model module, so Base.metadata is complete.
import protcellar.infrastructure.persistence.sqlalchemy.metadata  # noqa: F401
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.base import Base
from protcellar.infrastructure.sentinel.settings import SentinelSettings

MANIFEST_NAME = "manifest.json"

# Machine-local operational/compliance history — never part of a replica.
# No domain table has an FK into this set (verified: only audit tables
# reference audit_operations), so skipping them cannot dangle a reference.
EXCLUDED_TABLES = frozenset(
    {
        "audit_entries",
        "audit_operations",
        "electronic_signatures",
        "import_runs",
        "import_uploads",
    }
)


def replicated_tables() -> list[Table]:
    """All tables to replicate, in FK-dependency (insert-safe) order."""
    return [t for t in Base.metadata.sorted_tables if t.name not in EXCLUDED_TABLES]


def _json_default(value: object) -> str:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__} for export")


async def export_data(output: Path) -> None:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    counts: dict[str, int] = {}
    foreign_workspace_ids: set[str] = set()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tables_dir = Path(tmp) / "tables"
            tables_dir.mkdir()

            async with engine.connect() as conn:
                schema_rev = (
                    await conn.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar_one()
                for table in replicated_tables():
                    has_workspace = "workspace_id" in table.columns
                    n = 0
                    with (tables_dir / f"{table.name}.jsonl").open("w") as f:
                        result = await conn.stream(select(table))
                        async for row in result:
                            record = dict(row._mapping)
                            if has_workspace and record["workspace_id"] != SHARED_WORKSPACE_ID:
                                foreign_workspace_ids.add(str(record["workspace_id"]))
                            f.write(json.dumps(record, default=_json_default) + "\n")
                            n += 1
                    counts[table.name] = n
                    print(f"  {table.name}: {n} rows")

            manifest = {
                "schema_rev": schema_rev,
                "exported_at": dt.datetime.now(dt.UTC).isoformat(),
                "source_service_name": SentinelSettings().service_name,
                "tables": counts,
                "excluded_tables": sorted(EXCLUDED_TABLES),
                # Sentinel workspace ids from the source install; the importer
                # must remap these to a workspace in the target's Sentinel.
                "foreign_workspace_ids": sorted(foreign_workspace_ids),
            }
            (Path(tmp) / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))

            with tarfile.open(output, "w:gz") as tar:
                tar.add(Path(tmp) / MANIFEST_NAME, arcname=MANIFEST_NAME)
                for table in replicated_tables():
                    path = tables_dir / f"{table.name}.jsonl"
                    tar.add(path, arcname=f"tables/{table.name}.jsonl")
    finally:
        await engine.dispose()

    total = sum(counts.values())
    size_mb = output.stat().st_size / 1_000_000
    print(f"\nExported {total} rows from {len(counts)} tables to {output} ({size_mb:.1f} MB)")
    if foreign_workspace_ids:
        print(
            f"Contains rows from {len(foreign_workspace_ids)} non-shared workspace(s); "
            "importers must pass --workspace <their-workspace-uuid>."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(f"protcellar-data-{dt.date.today().isoformat()}.tar.gz"),
        help="Output archive path (default: protcellar-data-<today>.tar.gz)",
    )
    args = parser.parse_args()
    asyncio.run(export_data(args.output))


if __name__ == "__main__":
    main()
