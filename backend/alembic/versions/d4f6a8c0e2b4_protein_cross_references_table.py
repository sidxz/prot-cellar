"""protein cross references table

Revision ID: d4f6a8c0e2b4
Revises: c2e4a6f8b0d2
Create Date: 2026-06-20 08:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4f6a8c0e2b4'
down_revision: Union[str, None] = 'c2e4a6f8b0d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'protein_cross_references',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('database', sa.String(length=64), nullable=False),
        sa.Column('accession', sa.String(length=128), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.String(length=64), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_cross_references_protein_id'), 'protein_cross_references', ['protein_id'], unique=False)
    op.create_index(op.f('ix_protein_cross_references_database'), 'protein_cross_references', ['database'], unique=False)
    op.create_index('ix_protein_xrefs_db_accession', 'protein_cross_references', ['database', 'accession'], unique=False)
    op.execute(
        """
        INSERT INTO protein_cross_references
            (id, protein_id, database, accession, properties, evidence, created_at, updated_at)
        SELECT gen_random_uuid(), p.id, elem->>'database', elem->>'accession',
               elem->'properties', elem->>'evidence', now(), now()
        FROM proteins p, json_array_elements(p.cross_references) AS elem
        WHERE p.cross_references IS NOT NULL
        """
    )
    op.drop_column('proteins', 'cross_references')


def downgrade() -> None:
    op.add_column('proteins', sa.Column('cross_references', sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE proteins p SET cross_references = sub.arr
        FROM (
            SELECT protein_id,
                   json_agg(json_build_object(
                       'database', database, 'accession', accession,
                       'properties', properties, 'evidence', evidence)) AS arr
            FROM protein_cross_references GROUP BY protein_id
        ) sub
        WHERE p.id = sub.protein_id
        """
    )
    op.drop_index('ix_protein_xrefs_db_accession', table_name='protein_cross_references')
    op.drop_index(op.f('ix_protein_cross_references_database'), table_name='protein_cross_references')
    op.drop_index(op.f('ix_protein_cross_references_protein_id'), table_name='protein_cross_references')
    op.drop_table('protein_cross_references')
