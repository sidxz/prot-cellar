"""hypomorph growth_defect optional

Revision ID: e15ace01b43d
Revises: 8c39f9e642ae
Create Date: 2026-08-10 11:46:54.751529

The column was required because every known source recorded a Yes/No determination.
A legacy corpus does not: it records ``Yes | No | TBD`` on all 195 hypomorphs, and the
10 ``TBD`` rows have no boolean to give. Rather than invent one, the owner decided
"not determined" is a legitimate, distinct state — the aggregate now accepts NULL
directly rather than collapsing it into False. The curator's literal word (including
the ``TBD`` cases this migration exists for) is kept separately, in each record's
``extensions["growth_defect_reported"]``.

downgrade() restores NOT NULL, but it is a one-way trip in practice: if any row has
been written with a NULL growth_defect since this upgraded (which is the entire point
of the change), Postgres will refuse the `SET NOT NULL` with a constraint violation.
An operator rolling back must first either backfill every NULL with a real value or
delete those rows — this migration does not choose that for them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e15ace01b43d'
down_revision: Union[str, None] = '8c39f9e642ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'hypomorphs', 'growth_defect',
        existing_type=sa.Boolean(),
        nullable=True,
    )


def downgrade() -> None:
    # Fails with a NOT NULL violation if any row has a NULL value — see the module
    # docstring. Backfill or delete those rows before downgrading.
    op.alter_column(
        'hypomorphs', 'growth_defect',
        existing_type=sa.Boolean(),
        nullable=False,
    )
