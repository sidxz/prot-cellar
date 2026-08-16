"""Round-trip test for the developer data-replication CLIs.

Proves the load-bearing behaviors against a real Postgres: UUIDs survive
verbatim, shared-workspace rows import unchanged, foreign-workspace rows are
adopted by ``--workspace``, user columns are rewritten by ``--user``, and
self-referencing rows (organisms.parent_id) insert even when the archive
lists children before parents.
"""

from __future__ import annotations

import json
import tarfile
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import TagModel
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models import OrganismModel
from protcellar.scripts.export_data import export_data, replicated_tables
from protcellar.scripts.import_data import import_data

# The testcontainer engine's asyncpg pool is session-scoped, so share its loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")

PARENT_ID = uuid.UUID("00000000-0000-0000-0000-00000000aaaa")
CHILD_ID = uuid.UUID("00000000-0000-0000-0000-00000000bbbb")
TAG_ID = uuid.UUID("00000000-0000-0000-0000-00000000cccc")
SOURCE_WS = uuid.UUID("00000000-0000-0000-0000-0000000000d1")
SOURCE_USER = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
TARGET_WS = uuid.UUID("00000000-0000-0000-0000-0000000000d2")
TARGET_USER = uuid.UUID("00000000-0000-0000-0000-0000000000e2")


def _reverse_organism_lines(archive: Path) -> None:
    """Rewrite the archive with organisms.jsonl reversed (children first)."""
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")
        organisms = Path(tmp) / "tables" / "organisms.jsonl"
        lines = organisms.read_text().splitlines(keepends=True)
        organisms.write_text("".join(reversed(lines)))
        with tarfile.open(archive, "w:gz") as tar:
            for path in sorted(Path(tmp).rglob("*")):
                if path.is_file():
                    tar.add(path, arcname=str(path.relative_to(tmp)))


async def test_export_import_round_trip(engine: AsyncEngine, tmp_path: Path) -> None:
    # Hermetic slate: earlier suite tests commit rows; exporting them would make
    # this test's archive (and any cross-workspace unique-key collisions in it)
    # depend on suite order.
    async with engine.begin() as conn:
        for table in reversed(replicated_tables()):
            await conn.execute(table.delete())

    async with engine.begin() as conn:
        await conn.execute(
            OrganismModel.__table__.insert(),
            [
                {
                    "id": PARENT_ID,
                    "workspace_id": SHARED_WORKSPACE_ID,
                    # executemany compiles from the first param set — keep keys
                    # identical across rows or later parent_ids are dropped.
                    "parent_id": None,
                    "rank": "species",
                    "scientific_name": "Replicatus parentis",
                    "source": "manual",
                },
                {
                    "id": CHILD_ID,
                    "workspace_id": SHARED_WORKSPACE_ID,
                    "parent_id": PARENT_ID,
                    "rank": "strain",
                    "scientific_name": "Replicatus filius",
                    "source": "manual",
                },
            ],
        )
        await conn.execute(
            TagModel.__table__.insert(),
            [
                {
                    "id": TAG_ID,
                    "workspace_id": SOURCE_WS,
                    "key": "stage",
                    "value": "hit",
                    "normalized_key": "stage",
                    "normalized_value": "hit",
                    "created_by": SOURCE_USER,
                }
            ],
        )

    archive = tmp_path / "replica.tar.gz"
    await export_data(archive)

    with tarfile.open(archive) as tar:
        manifest = json.load(tar.extractfile("manifest.json"))  # type: ignore[arg-type]
    assert str(SOURCE_WS) in manifest["foreign_workspace_ids"]
    assert manifest["tables"]["organisms"] >= 2
    assert "audit_entries" not in manifest["tables"]

    # Children before parents in the file must still import (multi-pass insert).
    _reverse_organism_lines(archive)

    # Non-empty target without --truncate must refuse.
    with pytest.raises(SystemExit, match="not empty"):
        await import_data(
            archive,
            workspace=TARGET_WS,
            user=TARGET_USER,
            truncate=False,
            skip_duar_check=True,
            force=False,
        )

    await import_data(
        archive,
        workspace=TARGET_WS,
        user=TARGET_USER,
        truncate=True,
        skip_duar_check=True,
        force=False,
    )

    async with engine.connect() as conn:
        child = (
            await conn.execute(
                select(OrganismModel.__table__).where(OrganismModel.__table__.c.id == CHILD_ID)
            )
        ).one()
        assert child.parent_id == PARENT_ID
        assert child.workspace_id == SHARED_WORKSPACE_ID  # shared rows untouched
        tag = (
            await conn.execute(select(TagModel.__table__).where(TagModel.__table__.c.id == TAG_ID))
        ).one()
        assert tag.workspace_id == TARGET_WS  # foreign workspace adopted
        assert tag.created_by == TARGET_USER  # user column rewritten
        assert tag.key == "stage" and tag.value == "hit"

    # Default (no --workspace/--user): same-Duar mirror, ids imported verbatim.
    await import_data(
        archive,
        workspace=None,
        user=None,
        truncate=True,
        skip_duar_check=True,
        force=False,
    )
    async with engine.connect() as conn:
        tag = (
            await conn.execute(select(TagModel.__table__).where(TagModel.__table__.c.id == TAG_ID))
        ).one()
        assert tag.workspace_id == SOURCE_WS
        assert tag.created_by == SOURCE_USER

    async with engine.begin() as conn:
        await conn.execute(delete(TagModel.__table__))
        await conn.execute(
            delete(OrganismModel.__table__).where(OrganismModel.__table__.c.id == CHILD_ID)
        )
        await conn.execute(
            delete(OrganismModel.__table__).where(OrganismModel.__table__.c.id == PARENT_ID)
        )
