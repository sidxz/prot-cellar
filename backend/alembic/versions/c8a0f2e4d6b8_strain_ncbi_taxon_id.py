"""strain: replace strain_organism_id with ncbi_taxon_id

The strain taxon is no longer modelled as a separate Organism node — the
Strain aggregate is the sole representation of a strain, carrying the NCBI
strain taxon id as a scalar instead of a FK to a second organism row.

Revision ID: c8a0f2e4d6b8
Revises: 31fb243c1b94
Create Date: 2026-06-21 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a0f2e4d6b8'
down_revision: Union[str, None] = '31fb243c1b94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('strains_strain_organism_id_fkey', 'strains', type_='foreignkey')
    op.drop_column('strains', 'strain_organism_id')
    op.add_column('strains', sa.Column('ncbi_taxon_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_strains_ncbi_taxon_id'), 'strains', ['ncbi_taxon_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_strains_ncbi_taxon_id'), table_name='strains')
    op.drop_column('strains', 'ncbi_taxon_id')
    op.add_column(
        'strains',
        sa.Column('strain_organism_id', sa.Uuid(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        'strains_strain_organism_id_fkey',
        'strains',
        'organisms',
        ['strain_organism_id'],
        ['id'],
    )
