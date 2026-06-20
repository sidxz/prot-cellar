"""protein keywords table

Revision ID: a8c0e2f4b6d8
Revises: e6f8a0c2d4b6
Create Date: 2026-06-19 21:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a8c0e2f4b6d8'
down_revision: Union[str, None] = 'e6f8a0c2d4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protein_keywords',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('kw_id', sa.String(length=16), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_keywords_protein_id'), 'protein_keywords', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_keywords_kw_id'), 'protein_keywords', ['kw_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_protein_keywords_kw_id'), table_name='protein_keywords')
    op.drop_index(op.f('ix_protein_keywords_protein_id'), table_name='protein_keywords')
    op.drop_table('protein_keywords')
