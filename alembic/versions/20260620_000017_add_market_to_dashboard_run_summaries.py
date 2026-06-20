"""Add market column to dashboard_run_summaries.

Revision ID: 20260620_000017
Revises: 20260620_000016
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "20260620_000017"
down_revision = "20260620_000016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dashboard_run_summaries",
        sa.Column("market", sa.String(16), nullable=False, server_default="a"),
    )


def downgrade() -> None:
    op.drop_column("dashboard_run_summaries", "market")
