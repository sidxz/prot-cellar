"""move non-reference rows out of the shared workspace

Revision ID: d2b5f9c8e314
Revises: c1a4e8b7d203
Create Date: 2026-08-08 00:00:00.000000

Reference data stays shared. Private observations, workspace artifacts and
workspace-owned entities move to the workspace that owns them. This is the only
step in the tenancy work that changes what anyone can see, and at time of
writing it changes it for four rows: one private_comm vulnerability (the
target-biology public/private split) plus all three existing import_runs
(globally readable via readable_by while under SHARED, workspace-only after).
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2b5f9c8e314'
down_revision: Union[str, None] = 'c1a4e8b7d203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHARED = 'a577f0f9-b1fb-53b6-be5d-49bcb500adeb'

# Target-biology tables whose rows move when the provenance is not public.
_OBSERVATION_TABLES = [
    "essentiality_records",
    "vulnerability_records",
    "hypomorphs",
    "crispri_strains",
    "resistance_mutations",
    "protein_productions",
    "protein_activity_assays",
    "unpublished_structures",
]

# Whole tables that are workspace artifacts, never reference data.
_WORKSPACE_TABLES = ["import_runs", "import_uploads", "tags", "targets", "organizations"]


def _target_workspace() -> str:
    value = os.environ.get("MIGRATION_TARGET_WORKSPACE_ID")
    if not value:
        raise RuntimeError(
            "MIGRATION_TARGET_WORKSPACE_ID must name the workspace that inherits "
            "the existing non-reference data. There is no safe default."
        )
    return value


def upgrade() -> None:
    target = _target_workspace()
    for table in _OBSERVATION_TABLES:
        # Bare bind params compared against a uuid column trip the same asyncpg
        # gotcha c1a4e8b7d203 hit (untyped params come across as text and don't
        # implicitly compare against uuid) — CAST explicitly, same as that migration.
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = CAST(:target AS uuid) "
                f"WHERE workspace_id = CAST(:shared AS uuid) "
                f"AND COALESCE(provenance->>'source_type', '') "
                f"NOT IN ('published', 'preprint')"
            ).bindparams(target=target, shared=_SHARED)
        )
    for table in _WORKSPACE_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = CAST(:target AS uuid) "
                f"WHERE workspace_id = CAST(:shared AS uuid)"
            ).bindparams(target=target, shared=_SHARED)
        )


def downgrade() -> None:
    """Reverse the reclassification — but not a scoped inverse.

    This moves EVERY row currently under the target workspace back to SHARED,
    unconditionally, across all 13 tables. It cannot tell rows upgrade() moved
    apart from rows created natively under the target workspace afterwards
    through ordinary use (new tags, targets, import runs, private
    target-biology records written via auth.workspace_id) — it moves all of
    them.

    Safe ONLY immediately after upgrade(), with no intervening writes. Run
    against a database with real activity, it makes every one of those
    workspace-private rows world-readable — the exact leak this migration
    exists to close, in reverse. Re-running upgrade() afterwards does NOT
    undo the damage for rows whose provenance is public: upgrade() only pulls
    non-public-provenance rows back out of SHARED, so a natively-created
    target-biology row that happens to carry published/preprint provenance
    stays stranded at SHARED — readable by everyone and, since owned_by
    excludes SHARED, no longer editable by the tenant that created it.
    """
    target = _target_workspace()
    for table in _OBSERVATION_TABLES + _WORKSPACE_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = CAST(:shared AS uuid) "
                f"WHERE workspace_id = CAST(:target AS uuid)"
            ).bindparams(target=target, shared=_SHARED)
        )
