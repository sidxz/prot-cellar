"""add gene.strain_id (strain-scope genes, mirroring proteins)

Genes are genomic features that belong to a specific strain's genome (e.g.
H37Rv Rv0667 vs CDC1551 MT0695 are distinct genes with the same name). Proteins
already carry strain-specificity via ``strain_id``; genes did not, so multiple
strains of a species collapsed into indistinguishable duplicate gene rows.

This adds ``genes.strain_id`` (nullable — null for single-genome species like
human) and backfills it from each gene's already-resolved protein strain.

Revision ID: a7f2e9c4b1d8
Revises: 527794c94074
Create Date: 2026-07-16 12:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7f2e9c4b1d8"
down_revision: Union[str, None] = "527794c94074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("genes", sa.Column("strain_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_genes_strain_id"), "genes", ["strain_id"], unique=False)
    op.create_foreign_key("genes_strain_id_fkey", "genes", "strains", ["strain_id"], ["id"])
    # Backfill: a gene inherits the strain already resolved on its protein(s).
    # A gene normally maps to one strain; if a legacy collapsed row links proteins
    # from several strains, pick the lowest id deterministically (min) rather than
    # letting the planner choose an arbitrary joined row.
    op.execute(
        "UPDATE genes SET strain_id = sub.strain_id FROM ("
        "  SELECT gene_id, min(strain_id::text)::uuid AS strain_id"
        "  FROM proteins WHERE gene_id IS NOT NULL AND strain_id IS NOT NULL"
        "  GROUP BY gene_id"
        ") sub WHERE sub.gene_id = genes.id"
    )


def downgrade() -> None:
    op.drop_constraint("genes_strain_id_fkey", "genes", type_="foreignkey")
    op.drop_index(op.f("ix_genes_strain_id"), table_name="genes")
    op.drop_column("genes", "strain_id")
