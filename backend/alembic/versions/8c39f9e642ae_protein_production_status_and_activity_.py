"""protein production status and activity measured optional

Revision ID: 8c39f9e642ae
Revises: e3c9a1f7b508
Create Date: 2026-08-10 10:05:15.894337

Both columns were required because every known source recorded them. A legacy corpus
import does not: it has a construct description/method/purity/date for production but
no production status, and a prose assay description/method/throughput for activity but
no short "what activity" label. Rather than invent a value, the owner decided both are
optional — the aggregates already normalise a blank/whitespace value to NULL, so this
migration only has to stop rejecting NULL itself.

downgrade() restores NOT NULL, but it is a one-way trip in practice: if any row has been
written with a NULL status/activity_measured since this upgraded (which is the entire
point of the change), Postgres will refuse the `SET NOT NULL` with a constraint
violation. An operator rolling back must first either backfill every NULL with a real
value or delete those rows — this migration does not choose that for them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c39f9e642ae'
down_revision: Union[str, None] = 'e3c9a1f7b508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'protein_productions', 'status',
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.alter_column(
        'protein_activity_assays', 'activity_measured',
        existing_type=sa.String(length=128),
        nullable=True,
    )


def downgrade() -> None:
    # Fails with a NOT NULL violation if any row has a NULL value — see the module
    # docstring. Backfill or delete those rows before downgrading.
    op.alter_column(
        'protein_productions', 'status',
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        'protein_activity_assays', 'activity_measured',
        existing_type=sa.String(length=128),
        nullable=False,
    )
