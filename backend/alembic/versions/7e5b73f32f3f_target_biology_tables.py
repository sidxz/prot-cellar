"""target biology tables

Revision ID: 7e5b73f32f3f
Revises: f1a3c5e7b9d2
Create Date: 2026-07-15 22:06:45.823213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7e5b73f32f3f'
down_revision: Union[str, None] = 'f1a3c5e7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('crispri_strains',
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('target_gene_id', sa.Uuid(), nullable=False),
    sa.Column('provenance', sa.JSON(), nullable=False),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_crispri_strains_name'), 'crispri_strains', ['name'], unique=False)
    op.create_index(op.f('ix_crispri_strains_target_gene_id'), 'crispri_strains', ['target_gene_id'], unique=False)
    op.create_index(op.f('ix_crispri_strains_workspace_id'), 'crispri_strains', ['workspace_id'], unique=False)
    op.create_table('essentiality_records',
    sa.Column('gene_id', sa.Uuid(), nullable=False),
    sa.Column('classification', sa.String(length=32), nullable=False),
    sa.Column('condition', sa.String(length=128), nullable=True),
    sa.Column('method', sa.String(length=64), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=False),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_essentiality_records_classification'), 'essentiality_records', ['classification'], unique=False)
    op.create_index(op.f('ix_essentiality_records_gene_id'), 'essentiality_records', ['gene_id'], unique=False)
    op.create_index(op.f('ix_essentiality_records_method'), 'essentiality_records', ['method'], unique=False)
    op.create_index(op.f('ix_essentiality_records_workspace_id'), 'essentiality_records', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_essentiality_records_workspace_id'), table_name='essentiality_records')
    op.drop_index(op.f('ix_essentiality_records_method'), table_name='essentiality_records')
    op.drop_index(op.f('ix_essentiality_records_gene_id'), table_name='essentiality_records')
    op.drop_index(op.f('ix_essentiality_records_classification'), table_name='essentiality_records')
    op.drop_table('essentiality_records')
    op.drop_index(op.f('ix_crispri_strains_workspace_id'), table_name='crispri_strains')
    op.drop_index(op.f('ix_crispri_strains_target_gene_id'), table_name='crispri_strains')
    op.drop_index(op.f('ix_crispri_strains_name'), table_name='crispri_strains')
    op.drop_table('crispri_strains')
