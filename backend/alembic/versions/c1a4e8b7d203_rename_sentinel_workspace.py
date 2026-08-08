"""rename the sentinel workspace to a distinct shared workspace id

Revision ID: c1a4e8b7d203
Revises: b3d7f1c9a204
Create Date: 2026-08-08 00:00:00.000000

The reserved sentinel was the null UUID, which is indistinguishable from an
unset column. Under a real tenancy check that is a leak waiting to happen: a
forgotten assignment would make the row readable by every tenant. Swap it for a
distinct id so the same mistake makes a row readable by nobody instead.

Pure value swap. No read path filters by workspace yet, so visibility is
unchanged by construction.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1a4e8b7d203'
down_revision: Union[str, None] = 'b3d7f1c9a204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = '00000000-0000-0000-0000-000000000000'
_NEW = 'a577f0f9-b1fb-53b6-be5d-49bcb500adeb'

# Every table carrying workspace_id. Taken from the live catalog, not the models:
#   SELECT c.relname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
#    WHERE a.attname = 'workspace_id' AND c.relkind = 'r' AND NOT a.attisdropped;
_TABLES: list[str] = [
    "audit_operations",
    "essentiality_records",
    "crispri_strains",
    "vulnerability_records",
    "hypomorphs",
    "resistance_mutations",
    "protein_productions",
    "protein_activity_assays",
    "unpublished_structures",
    "genes",
    "proteins",
    "organisms",
    "strains",
    "proteomes",
    "targets",
    "tags",
    "import_runs",
    "import_uploads",
    "organizations",
    "workspace_enabled_plugins",
]


def _swap(old: str, new: str) -> None:
    for table in _TABLES:
        # asyncpg infers untyped bind params as text and won't implicitly
        # compare that against a uuid column — cast explicitly. CAST(...) is
        # used instead of the ``::uuid`` shorthand seen elsewhere in this
        # migration set (e.g. 67ee6b430f73) because a bind param immediately
        # followed by ``::`` confuses text()'s own parameter tokenizer.
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = CAST(:new AS uuid) "
                f"WHERE workspace_id = CAST(:old AS uuid)"
            ).bindparams(new=new, old=old)
        )


def upgrade() -> None:
    _swap(_OLD, _NEW)


def downgrade() -> None:
    _swap(_NEW, _OLD)
