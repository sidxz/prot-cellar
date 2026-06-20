"""proteome proteins membership table

Revision ID: c2e4a6f8b0d2
Revises: b0d2f4a6c8e0
Create Date: 2026-06-19 21:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2e4a6f8b0d2'
down_revision: Union[str, None] = 'b0d2f4a6c8e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'proteome_proteins',
        sa.Column('proteome_id', sa.Uuid(), nullable=False),
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['proteome_id'], ['proteomes.id'], ),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('proteome_id', 'protein_id', name='uq_proteome_protein'),
    )
    op.create_index(op.f('ix_proteome_proteins_proteome_id'), 'proteome_proteins', ['proteome_id'], unique=False)
    op.create_index(op.f('ix_proteome_proteins_protein_id'), 'proteome_proteins', ['protein_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proteome_proteins_protein_id'), table_name='proteome_proteins')
    op.drop_index(op.f('ix_proteome_proteins_proteome_id'), table_name='proteome_proteins')
    op.drop_table('proteome_proteins')
