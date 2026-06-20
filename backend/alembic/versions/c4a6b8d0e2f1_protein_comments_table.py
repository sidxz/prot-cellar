"""protein comments table

Revision ID: c4a6b8d0e2f1
Revises: b2e4f6a8c1d3
Create Date: 2026-06-19 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4a6b8d0e2f1'
down_revision: Union[str, None] = 'b2e4f6a8c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protein_comments',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('comment_type', sa.String(length=64), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_comments_protein_id'), 'protein_comments', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_comments_comment_type'), 'protein_comments', ['comment_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_protein_comments_comment_type'), table_name='protein_comments')
    op.drop_index(op.f('ix_protein_comments_protein_id'), table_name='protein_comments')
    op.drop_table('protein_comments')
