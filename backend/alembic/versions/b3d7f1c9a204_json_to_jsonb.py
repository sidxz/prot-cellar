"""convert every json column to jsonb

Revision ID: b3d7f1c9a204
Revises: 07a8ec2a2bd1
Create Date: 2026-08-07 00:00:00.000000

Postgres stores ``json`` as verbatim text and reparses it on every access. It
cannot be indexed, and it has no equality operator — so ``SELECT DISTINCT``,
``GROUP BY`` and ``ORDER BY`` all *error* on a json column today. ``jsonb`` is a
strict superset for how this schema uses these columns, and it is what makes the
``extensions`` bags on the target-biology records queryable at all.

The four reasons to prefer ``json`` do not apply here: nothing needs the document
preserved byte-for-byte, nothing depends on key order, Pydantic cannot emit
duplicate keys, and every one of these columns is read back into the app. The
type was inherited from the first column that used it, not chosen — the
``extensions`` columns even carry a note planning this change.

Portability is not a reason to keep ``json`` either: this schema already uses
ARRAY, GIN indexes, trigram operator classes and ``nulls_not_distinct``.

NOTE ON COST: this rewrites each table under ACCESS EXCLUSIVE. On the four large
tables (protein_features ~1.1M rows, protein_citations ~855k, protein_comments
~271k, proteins ~161k) that is minutes and roughly doubles their disk during the
rewrite. Run it in a maintenance window on any deployment holding real data.

No GIN indexes are added. Nothing queries inside these columns yet, and an index
costs write throughput and disk from the moment it exists. ``CREATE INDEX
CONCURRENTLY`` can add one without a lock whenever a real query turns up — the
type change is the part that gets more expensive the longer it waits.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3d7f1c9a204'
down_revision: Union[str, None] = '07a8ec2a2bd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every json column in the schema, taken from the live catalog rather than the
# models so nothing is missed:
#   SELECT c.relname, a.attname FROM pg_attribute a
#     JOIN pg_class c ON c.oid = a.attrelid JOIN pg_type t ON t.oid = a.atttypid
#    WHERE t.typname = 'json' AND a.attnum > 0
#      AND NOT a.attisdropped AND c.relkind = 'r';
_COLUMNS: list[tuple[str, str]] = [
    ("crispri_strains", "extensions"),
    ("crispri_strains", "provenance"),
    ("essentiality_records", "extensions"),
    ("essentiality_records", "provenance"),
    ("genes", "annotations"),
    ("genes", "cross_references"),
    ("hypomorphs", "extensions"),
    ("hypomorphs", "provenance"),
    ("import_runs", "params"),
    ("import_runs", "summary"),
    ("protein_activity_assays", "extensions"),
    ("protein_activity_assays", "provenance"),
    ("protein_citations", "authors"),
    ("protein_citations", "positions"),
    ("protein_citations", "reference_comments"),
    ("protein_comments", "evidence"),
    ("protein_comments", "payload"),
    ("protein_cross_references", "properties"),
    ("protein_features", "evidence"),
    ("protein_features", "ligand"),
    ("protein_productions", "extensions"),
    ("protein_productions", "provenance"),
    ("proteins", "protein_names"),
    ("resistance_mutations", "compound"),
    ("resistance_mutations", "extensions"),
    ("resistance_mutations", "provenance"),
    ("strains", "strain_metadata"),
    ("targets", "cross_references"),
    ("unpublished_structures", "extensions"),
    ("unpublished_structures", "ligands"),
    ("unpublished_structures", "provenance"),
    ("vulnerability_records", "extensions"),
    ("vulnerability_records", "provenance"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=postgresql.JSONB(astext_type=sa.Text()),
            postgresql_using=f"{column}::jsonb",
        )


def downgrade() -> None:
    # Reversible in type, but not perfectly in content: jsonb has already
    # discarded insignificant whitespace, key order and duplicate keys. Nothing
    # in this schema depends on any of those — Pydantic defines key order at the
    # model and cannot emit duplicates — so the round trip is lossless in
    # practice, just not byte-for-byte.
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=postgresql.JSON(astext_type=sa.Text()),
            postgresql_using=f"{column}::json",
        )
