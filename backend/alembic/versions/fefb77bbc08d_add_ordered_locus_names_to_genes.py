"""add ordered_locus_names to genes

Revision ID: fefb77bbc08d
Revises: 67ee6b430f73
Create Date: 2026-07-28 19:02:40.998999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fefb77bbc08d'
down_revision: Union[str, None] = '67ee6b430f73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "genes",
        sa.Column("ordered_locus_names", postgresql.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("genes", "ordered_locus_names")
