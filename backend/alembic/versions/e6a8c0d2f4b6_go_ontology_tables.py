"""go ontology tables

Revision ID: e6a8c0d2f4b6
Revises: d4f6a8c0e2b4
Create Date: 2026-06-20 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e6a8c0d2f4b6'
down_revision: Union[str, None] = 'd4f6a8c0e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'go_terms',
        sa.Column('go_id', sa.String(length=12), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('namespace', sa.String(length=32), nullable=False),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('is_obsolete', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('replaced_by', sa.String(length=12), nullable=True),
        sa.Column('source', sa.String(length=16), server_default=sa.text("'go'"), nullable=False),
        sa.Column('source_version', sa.String(length=32), nullable=True),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_go_terms_go_id', 'go_terms', ['go_id'], unique=True)
    op.create_table(
        'go_edges',
        sa.Column('child_go_id', sa.String(length=12), nullable=False),
        sa.Column('parent_go_id', sa.String(length=12), nullable=False),
        sa.Column('relation', sa.String(length=16), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_go_edges_child_go_id'), 'go_edges', ['child_go_id'], unique=False)
    op.create_index(op.f('ix_go_edges_parent_go_id'), 'go_edges', ['parent_go_id'], unique=False)
    op.create_index('ix_go_edges_parent_child', 'go_edges', ['parent_go_id', 'child_go_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_go_edges_parent_child', table_name='go_edges')
    op.drop_index(op.f('ix_go_edges_parent_go_id'), table_name='go_edges')
    op.drop_index(op.f('ix_go_edges_child_go_id'), table_name='go_edges')
    op.drop_table('go_edges')
    op.drop_index('ix_go_terms_go_id', table_name='go_terms')
    op.drop_table('go_terms')
