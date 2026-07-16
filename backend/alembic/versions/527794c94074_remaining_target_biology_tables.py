"""remaining target biology tables

Revision ID: 527794c94074
Revises: b863e0affb9c
Create Date: 2026-07-15 23:10:49.145102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '527794c94074'
down_revision: Union[str, None] = 'b863e0affb9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('hypomorphs',
    sa.Column('gene_id', sa.Uuid(), nullable=False),
    sa.Column('growth_defect', sa.Boolean(), nullable=False),
    sa.Column('knockdown_strain_id', sa.Uuid(), nullable=True),
    sa.Column('growth_defect_severity', sa.String(length=64), nullable=True),
    sa.Column('condition', sa.String(length=128), nullable=True),
    sa.Column('method', sa.String(length=64), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hypomorphs_gene_id'), 'hypomorphs', ['gene_id'], unique=False)
    op.create_index(op.f('ix_hypomorphs_knockdown_strain_id'), 'hypomorphs', ['knockdown_strain_id'], unique=False)
    op.create_index(op.f('ix_hypomorphs_method'), 'hypomorphs', ['method'], unique=False)
    op.create_index(op.f('ix_hypomorphs_workspace_id'), 'hypomorphs', ['workspace_id'], unique=False)
    op.create_table('protein_activity_assays',
    sa.Column('protein_id', sa.Uuid(), nullable=False),
    sa.Column('activity_measured', sa.String(length=128), nullable=False),
    sa.Column('readout', sa.String(length=128), nullable=True),
    sa.Column('throughput', sa.String(length=64), nullable=True),
    sa.Column('condition', sa.String(length=128), nullable=True),
    sa.Column('method', sa.String(length=64), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_protein_activity_assays_activity_measured'), 'protein_activity_assays', ['activity_measured'], unique=False)
    op.create_index(op.f('ix_protein_activity_assays_protein_id'), 'protein_activity_assays', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_activity_assays_workspace_id'), 'protein_activity_assays', ['workspace_id'], unique=False)
    op.create_table('protein_productions',
    sa.Column('protein_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=64), nullable=False),
    sa.Column('expression_host', sa.String(length=128), nullable=True),
    sa.Column('purity', sa.Float(), nullable=True),
    sa.Column('condition', sa.String(length=128), nullable=True),
    sa.Column('method', sa.String(length=64), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_protein_productions_protein_id'), 'protein_productions', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_productions_status'), 'protein_productions', ['status'], unique=False)
    op.create_index(op.f('ix_protein_productions_workspace_id'), 'protein_productions', ['workspace_id'], unique=False)
    op.create_table('resistance_mutations',
    sa.Column('gene_id', sa.Uuid(), nullable=False),
    sa.Column('mutation', sa.String(length=128), nullable=False),
    sa.Column('compound', sa.JSON(), nullable=True),
    sa.Column('mic_shift', sa.Float(), nullable=True),
    sa.Column('parent_strain', sa.String(length=128), nullable=True),
    sa.Column('protein_coordinate', sa.String(length=64), nullable=True),
    sa.Column('method', sa.String(length=64), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resistance_mutations_gene_id'), 'resistance_mutations', ['gene_id'], unique=False)
    op.create_index(op.f('ix_resistance_mutations_method'), 'resistance_mutations', ['method'], unique=False)
    op.create_index(op.f('ix_resistance_mutations_mutation'), 'resistance_mutations', ['mutation'], unique=False)
    op.create_index(op.f('ix_resistance_mutations_workspace_id'), 'resistance_mutations', ['workspace_id'], unique=False)
    op.create_table('unpublished_structures',
    sa.Column('protein_id', sa.Uuid(), nullable=False),
    sa.Column('method', sa.String(length=64), nullable=True),
    sa.Column('resolution', sa.Float(), nullable=True),
    sa.Column('ligands', sa.JSON(), nullable=True),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('is_experimental', sa.Boolean(), nullable=False),
    sa.Column('provenance', sa.JSON(), nullable=True),
    sa.Column('extensions', sa.JSON(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unpublished_structures_method'), 'unpublished_structures', ['method'], unique=False)
    op.create_index(op.f('ix_unpublished_structures_protein_id'), 'unpublished_structures', ['protein_id'], unique=False)
    op.create_index(op.f('ix_unpublished_structures_workspace_id'), 'unpublished_structures', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_unpublished_structures_workspace_id'), table_name='unpublished_structures')
    op.drop_index(op.f('ix_unpublished_structures_protein_id'), table_name='unpublished_structures')
    op.drop_index(op.f('ix_unpublished_structures_method'), table_name='unpublished_structures')
    op.drop_table('unpublished_structures')
    op.drop_index(op.f('ix_resistance_mutations_workspace_id'), table_name='resistance_mutations')
    op.drop_index(op.f('ix_resistance_mutations_mutation'), table_name='resistance_mutations')
    op.drop_index(op.f('ix_resistance_mutations_method'), table_name='resistance_mutations')
    op.drop_index(op.f('ix_resistance_mutations_gene_id'), table_name='resistance_mutations')
    op.drop_table('resistance_mutations')
    op.drop_index(op.f('ix_protein_productions_workspace_id'), table_name='protein_productions')
    op.drop_index(op.f('ix_protein_productions_status'), table_name='protein_productions')
    op.drop_index(op.f('ix_protein_productions_protein_id'), table_name='protein_productions')
    op.drop_table('protein_productions')
    op.drop_index(op.f('ix_protein_activity_assays_workspace_id'), table_name='protein_activity_assays')
    op.drop_index(op.f('ix_protein_activity_assays_protein_id'), table_name='protein_activity_assays')
    op.drop_index(op.f('ix_protein_activity_assays_activity_measured'), table_name='protein_activity_assays')
    op.drop_table('protein_activity_assays')
    op.drop_index(op.f('ix_hypomorphs_workspace_id'), table_name='hypomorphs')
    op.drop_index(op.f('ix_hypomorphs_method'), table_name='hypomorphs')
    op.drop_index(op.f('ix_hypomorphs_knockdown_strain_id'), table_name='hypomorphs')
    op.drop_index(op.f('ix_hypomorphs_gene_id'), table_name='hypomorphs')
    op.drop_table('hypomorphs')
