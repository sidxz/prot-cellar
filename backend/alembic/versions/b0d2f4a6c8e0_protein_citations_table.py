"""protein citations table

Revision ID: b0d2f4a6c8e0
Revises: a8c0e2f4b6d8
Create Date: 2026-06-19 21:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b0d2f4a6c8e0'
down_revision: Union[str, None] = 'a8c0e2f4b6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protein_citations',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('citation_type', sa.String(length=64), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('journal', sa.String(length=512), nullable=True),
        sa.Column('authors', sa.JSON(), nullable=True),
        sa.Column('publication_date', sa.String(length=32), nullable=True),
        sa.Column('pubmed_id', sa.String(length=32), nullable=True),
        sa.Column('doi', sa.String(length=128), nullable=True),
        sa.Column('reference_number', sa.Integer(), nullable=True),
        sa.Column('positions', sa.JSON(), nullable=True),
        sa.Column('reference_comments', sa.JSON(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_citations_protein_id'), 'protein_citations', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_citations_pubmed_id'), 'protein_citations', ['pubmed_id'], unique=False)
    op.create_index(op.f('ix_protein_citations_doi'), 'protein_citations', ['doi'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_protein_citations_doi'), table_name='protein_citations')
    op.drop_index(op.f('ix_protein_citations_pubmed_id'), table_name='protein_citations')
    op.drop_index(op.f('ix_protein_citations_protein_id'), table_name='protein_citations')
    op.drop_table('protein_citations')
