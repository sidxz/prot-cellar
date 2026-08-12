"""CLI: restore an archive produced by ``export_data.py`` into this developer's database.

Every entity keeps its original UUID, and by default workspace/user ids import
verbatim — right whenever both installs talk to the same Sentinel. If your
Sentinel is a different install (its workspace and user UUIDs differ), pass
``--workspace``/``--user`` with ids from *your* Sentinel: non-shared rows are
reassigned to them, while rows of the shared reference workspace always import
unchanged (that id is the same deterministic constant everywhere).

Before touching the database the importer registers the ``protcellar:*`` RBAC
actions in your Sentinel under *your* app name (``SENTINEL_SERVICE_NAME``) —
the one piece of prot-cellar state that lives in Sentinel — which doubles as
proof that your service name/key are actually registered there.

Usage:
    uv run python -m protcellar.scripts.import_data archive.tar.gz \
        [--workspace UUID] [--user UUID] [--truncate] [--skip-sentinel-check] [--force]
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime as dt
import json
import tarfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, Table, Uuid, select, text
from sqlalchemy.exc import NoResultFound, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.sentinel.auth import create_sentinel, register_service_actions
from protcellar.infrastructure.sentinel.settings import SentinelSettings
from protcellar.scripts.export_data import MANIFEST_NAME, replicated_tables

_BATCH_SIZE = 1000
# Sentinel user-UUID columns present in replicated tables (audit tables, which
# hold user_id, are never exported).
_USER_COLUMNS = {"created_by", "assigned_by", "enabled_by"}


def _self_fk_columns(table: Table) -> list[str]:
    """Columns referencing the table's own PK (e.g. organisms.parent_id)."""
    return [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]


async def _insert_self_referencing(
    conn: AsyncConnection, table: Table, records: list[dict[str, Any]], self_cols: list[str]
) -> int:
    """Insert parents before children — sorted_tables can't order rows *within* a table."""
    pk = next(iter(table.primary_key.columns)).name
    inserted: set[Any] = set()
    pending = records
    while pending:
        ready = [
            r
            for r in pending
            if all(r[c] is None or r[c] in inserted for c in self_cols)
        ]
        if not ready:
            raise SystemExit(
                f"Cannot order rows of '{table.name}': self-referencing cycle or "
                "reference to a row missing from the archive."
            )
        for i in range(0, len(ready), _BATCH_SIZE):
            await conn.execute(table.insert(), ready[i : i + _BATCH_SIZE])
        inserted.update(r[pk] for r in ready)
        pending = [r for r in pending if r[pk] not in inserted]
    return len(records)


def _coercers(table: Table) -> dict[str, Any]:
    """Per-column parsers turning JSONL strings back into DB-ready values."""
    out: dict[str, Any] = {}
    for col in table.columns:
        if isinstance(col.type, Uuid):
            out[col.name] = uuid.UUID
        elif isinstance(col.type, DateTime):
            out[col.name] = dt.datetime.fromisoformat
        elif isinstance(col.type, Date):
            out[col.name] = dt.date.fromisoformat
    return out


async def _check_schema(conn: AsyncConnection, manifest: dict[str, Any], force: bool) -> None:
    try:
        rev = (
            await conn.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
    except (ProgrammingError, NoResultFound):
        raise SystemExit(
            "Target database has no schema. Run: uv run alembic upgrade head"
        ) from None
    if rev != manifest["schema_rev"] and not force:
        raise SystemExit(
            f"Schema mismatch: archive was exported at revision {manifest['schema_rev']}, "
            f"this database is at {rev}. Run `git pull` + `uv run alembic upgrade head` "
            "(or pass --force if you know the difference is harmless)."
        )


async def _check_sentinel() -> None:
    """Register our RBAC actions under this developer's own Sentinel app.

    Failure means their SENTINEL_* env vars don't match a registered service
    app in their Sentinel — the exact misconfiguration this catches early.
    """
    settings = SentinelSettings()
    sentinel = create_sentinel(settings)
    # Mirror the app's boot order (see sentinel.lifespan): whoami discovers
    # realm membership and re-points the roles client at the realm scope —
    # without it, registering under the bare app name 403s for realm members.
    await sentinel.fetch_whoami()
    ok = await register_service_actions(sentinel)
    with contextlib.suppress(Exception):
        await sentinel.roles.close()
    if not ok:
        raise SystemExit(
            f"Sentinel check failed: could not register service actions at "
            f"{settings.url} as '{settings.service_name}'.\n"
            "Verify SENTINEL_URL / SENTINEL_SERVICE_NAME / SENTINEL_SERVICE_KEY in "
            "backend/.env match your own Sentinel app registration (your app name "
            "need not match the exporter's). Or pass --skip-sentinel-check."
        )


async def import_data(
    archive: Path,
    workspace: uuid.UUID | None,
    user: uuid.UUID | None,
    truncate: bool,
    skip_sentinel_check: bool,
    force: bool,
) -> None:
    with tarfile.open(archive) as tar:
        manifest = json.load(tar.extractfile(MANIFEST_NAME))  # type: ignore[arg-type]

        if manifest["foreign_workspace_ids"] and workspace is None:
            print(
                "NOTE: importing non-shared workspace id(s) "
                f"{manifest['foreign_workspace_ids']} verbatim. If your Sentinel is not "
                "the exporter's, those rows will be invisible until you re-import with "
                "--workspace <uuid> from YOUR Sentinel."
            )
        if workspace is not None and len(manifest["foreign_workspace_ids"]) > 1:
            print(
                f"NOTE: collapsing {len(manifest['foreign_workspace_ids'])} source "
                "workspaces into one; identical natural keys across them would abort "
                "the import (it is atomic — nothing is written on failure)."
            )
        unknown = set(manifest["tables"]) - {t.name for t in replicated_tables()}
        if unknown:
            print(f"WARNING: archive tables unknown to this code, skipped: {sorted(unknown)}")

        if not skip_sentinel_check:
            await _check_sentinel()
            print("Sentinel: service actions registered OK")

        engine = create_async_engine(DatabaseSettings().database_url)  # type: ignore[call-arg]
        try:
            async with engine.connect() as conn:
                await _check_schema(conn, manifest, force)
                if not truncate:
                    non_empty = []
                    for table in replicated_tables():
                        row = await conn.execute(select(text("1")).select_from(table).limit(1))
                        if row.first() is not None:
                            non_empty.append(table.name)
                    if non_empty:
                        raise SystemExit(
                            f"Target tables not empty: {non_empty}. "
                            "Pass --truncate to replace their contents."
                        )

            async with engine.begin() as conn:
                if truncate:
                    for table in reversed(replicated_tables()):
                        await conn.execute(table.delete())
                total = 0
                for table in replicated_tables():
                    member = f"tables/{table.name}.jsonl"
                    try:
                        f = tar.extractfile(member)
                    except KeyError:
                        print(f"  {table.name}: not in archive, skipped")
                        continue
                    assert f is not None
                    coerce = _coercers(table)
                    self_cols = _self_fk_columns(table)
                    batch: list[dict[str, Any]] = []
                    n = 0
                    for raw in f:
                        record: dict[str, Any] = json.loads(raw)
                        for name, fn in coerce.items():
                            if record.get(name) is not None:
                                record[name] = fn(record[name])
                        if (
                            workspace is not None
                            and record.get("workspace_id") not in (None, SHARED_WORKSPACE_ID)
                        ):
                            record["workspace_id"] = workspace
                        if user is not None:
                            for col in _USER_COLUMNS & record.keys():
                                if record[col] is not None:
                                    record[col] = user
                        batch.append(record)
                        if not self_cols and len(batch) >= _BATCH_SIZE:
                            await conn.execute(table.insert(), batch)
                            n += len(batch)
                            batch = []
                    if self_cols:
                        n = await _insert_self_referencing(conn, table, batch, self_cols)
                    elif batch:
                        await conn.execute(table.insert(), batch)
                        n += len(batch)
                    if n:
                        print(f"  {table.name}: {n} rows")
                    total += n
        finally:
            await engine.dispose()

    print(f"\nImported {total} rows from {archive} (schema {manifest['schema_rev']})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archive", type=Path, help="tar.gz produced by export_data.py")
    parser.add_argument(
        "--workspace",
        type=uuid.UUID,
        help="Remap all non-shared rows to this workspace UUID from YOUR Sentinel "
        "(default: keep workspace ids verbatim)",
    )
    parser.add_argument(
        "--user",
        type=uuid.UUID,
        help="User UUID from YOUR Sentinel; rewrites created_by/assigned_by/enabled_by",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing rows from replicated tables before importing",
    )
    parser.add_argument(
        "--skip-sentinel-check",
        action="store_true",
        help="Skip verifying/registering this app against your Sentinel",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Import despite an alembic schema revision mismatch",
    )
    args = parser.parse_args()
    asyncio.run(
        import_data(
            archive=args.archive,
            workspace=args.workspace,
            user=args.user,
            truncate=args.truncate,
            skip_sentinel_check=args.skip_sentinel_check,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
