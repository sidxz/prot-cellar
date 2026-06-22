"""import runs and uploads

Revision ID: 3a2dcd2950b4
Revises: c8a0f2e4d6b8
Create Date: 2026-06-22 14:07:25.380433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a2dcd2950b4'
down_revision: Union[str, None] = 'c8a0f2e4d6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_runs",
        sa.Column("import_type", sa.String(length=32), nullable=False),
        sa.Column("target_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=True),
        sa.Column("processed", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("source_version", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("upload_ref", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_runs_import_type", "import_runs", ["import_type"])
    op.create_index("ix_import_runs_target_key", "import_runs", ["target_key"])
    op.create_index("ix_import_runs_status", "import_runs", ["status"])
    op.create_index("ix_import_runs_workspace_id", "import_runs", ["workspace_id"])
    op.create_index("ix_import_runs_created_at", "import_runs", ["created_at"])
    op.create_table(
        "import_uploads",
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("import_uploads")
    for ix in ("created_at", "workspace_id", "status", "target_key", "import_type"):
        op.drop_index(f"ix_import_runs_{ix}", table_name="import_runs")
    op.drop_table("import_runs")
