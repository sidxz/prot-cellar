"""backfill proteomes.strain_id from member proteins

A UniProt proteome is strain-specific (e.g. UP000001584 = M. tuberculosis
H37Rv), but the importer created proteome rows without a strain_id, leaving it
NULL. Consumers that filter proteins by a proteome then fell back to the
organism and swept in every strain of the species.

The proteome's member proteins already carry the resolved strain, so copy it:
set ``proteomes.strain_id`` from the member proteins' strain. ``min()``
disambiguates the (shouldn't-happen) mixed-strain case deterministically; a
proteome with no members (e.g. the human reference) stays NULL. Only fills rows
that are currently NULL, so it is safe and idempotent. The companion importer
change populates strain_id directly for future imports.

Revision ID: 67ee6b430f73
Revises: 713bff91ff30
Create Date: 2026-07-28 10:11:10.471453

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '67ee6b430f73'
down_revision: Union[str, None] = '713bff91ff30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A proteome inherits the strain already resolved on its member proteins.
    op.execute(
        "UPDATE proteomes SET strain_id = sub.strain_id FROM ("
        "  SELECT pp.proteome_id, min(p.strain_id::text)::uuid AS strain_id"
        "  FROM proteome_proteins pp JOIN proteins p ON p.id = pp.protein_id"
        "  WHERE p.strain_id IS NOT NULL"
        "  GROUP BY pp.proteome_id"
        ") sub WHERE sub.proteome_id = proteomes.id AND proteomes.strain_id IS NULL"
    )


def downgrade() -> None:
    # Data-only backfill of NULLs; the resolved strain link is not something to
    # revert, and there is no schema change to undo.
    pass
