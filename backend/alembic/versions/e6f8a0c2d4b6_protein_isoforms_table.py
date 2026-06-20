"""protein isoforms table

Revision ID: e6f8a0c2d4b6
Revises: c4a6b8d0e2f1
Create Date: 2026-06-19 21:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e6f8a0c2d4b6'
down_revision: Union[str, None] = 'c4a6b8d0e2f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protein_isoforms',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('isoform_accession', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=True),
        sa.Column('is_displayed', sa.Boolean(), nullable=False),
        sa.Column('sequence', sa.Text(), nullable=True),
        sa.Column('event', sa.String(length=64), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_isoforms_protein_id'), 'protein_isoforms', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_isoforms_isoform_accession'), 'protein_isoforms', ['isoform_accession'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_protein_isoforms_isoform_accession'), table_name='protein_isoforms')
    op.drop_index(op.f('ix_protein_isoforms_protein_id'), table_name='protein_isoforms')
    op.drop_table('protein_isoforms')
