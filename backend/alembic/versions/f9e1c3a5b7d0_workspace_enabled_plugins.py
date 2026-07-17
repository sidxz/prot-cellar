"""workspace enabled plugins

Revision ID: f9e1c3a5b7d0
Revises: b2c4d6e8f0a1
Create Date: 2026-07-16 23:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9e1c3a5b7d0'
down_revision: Union[str, None] = 'b2c4d6e8f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_enabled_plugins",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("plugin_id", sa.String(length=100), nullable=False),
        sa.Column(
            "enabled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("enabled_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("workspace_id", "plugin_id"),
    )


def downgrade() -> None:
    op.drop_table("workspace_enabled_plugins")
