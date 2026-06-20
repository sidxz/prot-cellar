"""protein features table

Revision ID: b2e4f6a8c1d3
Revises: d3f8c2a1b9e4
Create Date: 2026-06-19 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2e4f6a8c1d3'
down_revision: Union[str, None] = 'd3f8c2a1b9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protein_features',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('feature_type', sa.String(length=64), nullable=False),
        sa.Column('start_pos', sa.Integer(), nullable=True),
        sa.Column('end_pos', sa.Integer(), nullable=True),
        sa.Column('start_modifier', sa.String(length=32), nullable=True),
        sa.Column('end_modifier', sa.String(length=32), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_id', sa.String(length=64), nullable=True),
        sa.Column('ligand', sa.JSON(), nullable=True),
        sa.Column('alternative_sequence', sa.Text(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_features_protein_id'), 'protein_features', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_features_feature_type'), 'protein_features', ['feature_type'], unique=False)
    op.create_index(op.f('ix_protein_features_feature_id'), 'protein_features', ['feature_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_protein_features_feature_id'), table_name='protein_features')
    op.drop_index(op.f('ix_protein_features_feature_type'), table_name='protein_features')
    op.drop_index(op.f('ix_protein_features_protein_id'), table_name='protein_features')
    op.drop_table('protein_features')
