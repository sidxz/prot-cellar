"""add orf_names to genes

Revision ID: 07a8ec2a2bd1
Revises: fefb77bbc08d
Create Date: 2026-07-28 20:06:28.984386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '07a8ec2a2bd1'
down_revision: Union[str, None] = 'fefb77bbc08d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "genes",
        sa.Column("orf_names", postgresql.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("genes", "orf_names")
