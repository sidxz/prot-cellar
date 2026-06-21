"""gene_locus_context

Revision ID: 31fb243c1b94
Revises: e6a8c0d2f4b6
Create Date: 2026-06-21 12:59:19.657224

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31fb243c1b94'
down_revision: Union[str, None] = 'e6a8c0d2f4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("genes", sa.Column("genomic_accession", sa.String(length=64), nullable=True))
    op.add_column("genes", sa.Column("genomic_start", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("genomic_end", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("genomic_strand", sa.String(length=1), nullable=True))
    op.add_column("genes", sa.Column("assembly", sa.String(length=64), nullable=True))
    op.add_column("genes", sa.Column("annotations", sa.JSON(), nullable=True))
    op.create_index(
        "ix_genes_locus", "genes", ["organism_id", "genomic_accession", "genomic_start"]
    )


def downgrade() -> None:
    op.drop_index("ix_genes_locus", table_name="genes")
    for col in (
        "annotations",
        "assembly",
        "genomic_strand",
        "genomic_end",
        "genomic_start",
        "genomic_accession",
    ):
        op.drop_column("genes", col)
