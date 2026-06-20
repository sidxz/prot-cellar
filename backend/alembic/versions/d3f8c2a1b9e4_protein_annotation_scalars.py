"""protein annotation scalars

Revision ID: d3f8c2a1b9e4
Revises: 6d6ec789aaae
Create Date: 2026-06-19 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3f8c2a1b9e4'
down_revision: Union[str, None] = '6d6ec789aaae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('proteins', sa.Column('annotation_score', sa.Integer(), nullable=True))
    op.add_column('proteins', sa.Column('fragment', sa.String(length=16), nullable=True))
    op.add_column('proteins', sa.Column('uniparc_id', sa.String(length=16), nullable=True))
    op.create_index(op.f('ix_proteins_uniparc_id'), 'proteins', ['uniparc_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proteins_uniparc_id'), table_name='proteins')
    op.drop_column('proteins', 'uniparc_id')
    op.drop_column('proteins', 'fragment')
    op.drop_column('proteins', 'annotation_score')
