"""add organisms.reference_strain_id (designated reference/preferred strain)

A species designates one reference strain (e.g. H37Rv for M. tuberculosis) —
the default shown/filtered in the gene dashboard, settable on the organism page
rather than hardcoded. Bare id (no FK) to avoid an organisms<->strains cycle.

Backfills species that have exactly one strain to that strain; multi-strain
species (which need a curated choice) are left null and set via the UI.

Revision ID: b2c4d6e8f0a1
Revises: a7f2e9c4b1d8
Create Date: 2026-07-16 13:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c4d6e8f0a1"
down_revision: Union[str, None] = "a7f2e9c4b1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organisms", sa.Column("reference_strain_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_organisms_reference_strain_id"),
        "organisms",
        ["reference_strain_id"],
        unique=False,
    )
    # A species with exactly one strain uses that strain as its reference.
    op.execute(
        "UPDATE organisms o SET reference_strain_id = s.id FROM strains s "
        "WHERE s.species_organism_id = o.id "
        "AND (SELECT count(*) FROM strains s2 WHERE s2.species_organism_id = o.id) = 1"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_organisms_reference_strain_id"), table_name="organisms")
    op.drop_column("organisms", "reference_strain_id")
