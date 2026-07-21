"""tagging — tags registry + 6 per-entity link tables + tag_links_all view.

Creates the tag registry (dedup unique index with NULLS NOT DISTINCT, trigram
GIN indexes for autocomplete) and six per-entity link tables (protein, gene,
target, organism, strain, proteome), plus a tag_links_all UNION ALL view for
cross-entity tag queries. Ported from chem-cellar's 047_tagging.py +
050_tagging_expansion.py, reduced to prot-cellar's 6 taggable entities. No
legacy-column backfill — prot-cellar has no pre-existing tags column to
migrate (unlike chem-cellar's molecules.tags).

Revision ID: 713bff91ff30
Revises: f9e1c3a5b7d0
Create Date: 2026-07-21 11:00:28.954054
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "713bff91ff30"
down_revision: Union[str, None] = "f9e1c3a5b7d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_link_table(name: str, entity_col: str, entity_table: str) -> None:
    op.create_table(
        name,
        sa.Column(
            entity_col,
            sa.Uuid(),
            sa.ForeignKey(f"{entity_table}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Uuid(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(f"ix_{name}_tag_id", name, ["tag_id"])


_VIEW_SQL = """
    CREATE VIEW tag_links_all AS
        SELECT 'Protein' AS entity_type, protein_id AS entity_id,
               tag_id, assigned_by, assigned_at FROM protein_tags
        UNION ALL
        SELECT 'Gene', gene_id, tag_id, assigned_by, assigned_at FROM gene_tags
        UNION ALL
        SELECT 'Target', target_id, tag_id, assigned_by, assigned_at FROM target_tags
        UNION ALL
        SELECT 'Organism', organism_id, tag_id, assigned_by, assigned_at FROM organism_tags
        UNION ALL
        SELECT 'Strain', strain_id, tag_id, assigned_by, assigned_at FROM strain_tags
        UNION ALL
        SELECT 'Proteome', proteome_id, tag_id, assigned_by, assigned_at FROM proteome_tags
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- tag registry ---
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.String(length=256), nullable=True),
        sa.Column("normalized_key", sa.String(length=128), nullable=False),
        sa.Column("normalized_value", sa.String(length=256), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_tags_workspace_id", "tags", ["workspace_id"])
    op.create_index("ix_tags_ws_created_by", "tags", ["workspace_id", "created_by"])
    # Unique dedup index — NULLS NOT DISTINCT so value-less tags collapse.
    op.create_index(
        "uq_tags_ws_norm",
        "tags",
        ["workspace_id", "normalized_key", "normalized_value"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )
    # Trigram GIN indexes for autocomplete.
    op.create_index(
        "ix_tags_norm_key_trgm",
        "tags",
        ["normalized_key"],
        postgresql_using="gin",
        postgresql_ops={"normalized_key": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_tags_norm_value_trgm",
        "tags",
        ["normalized_value"],
        postgresql_using="gin",
        postgresql_ops={"normalized_value": "gin_trgm_ops"},
    )

    # --- per-entity link tables ---
    _create_link_table("protein_tags", "protein_id", "proteins")
    _create_link_table("gene_tags", "gene_id", "genes")
    _create_link_table("target_tags", "target_id", "targets")
    _create_link_table("organism_tags", "organism_id", "organisms")
    _create_link_table("strain_tags", "strain_id", "strains")
    _create_link_table("proteome_tags", "proteome_id", "proteomes")

    # --- cross-type view ---
    op.execute(_VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS tag_links_all")
    op.drop_table("proteome_tags")
    op.drop_table("strain_tags")
    op.drop_table("organism_tags")
    op.drop_table("target_tags")
    op.drop_table("gene_tags")
    op.drop_table("protein_tags")
    op.drop_table("tags")
