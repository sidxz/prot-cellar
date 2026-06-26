"""widen protein_isoforms.event to text

Revision ID: f1a3c5e7b9d2
Revises: 3a2dcd2950b4
Create Date: 2026-06-23 00:00:00.000000

UniProt isoform ``event`` concatenates multiple alternative-products events
(e.g. "Alternative promoter usage, Alternative splicing, Alternative
initiation"), which exceeds the original String(64). Bacterial proteomes never
hit this; human (UP000005640) does — the import aborted mid-stream with
StringDataRightTruncationError. Widen to Text.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a3c5e7b9d2'
down_revision: Union[str, None] = '3a2dcd2950b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'protein_isoforms',
        'event',
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'protein_isoforms',
        'event',
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
