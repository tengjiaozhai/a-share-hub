"""Add alpha analysis runs table.

Revision ID: 20260622_000020
Revises: 20260622_000019
Create Date: 2026-06-22
"""

import sqlalchemy as sa
from alembic import op

revision = "20260622_000020"
down_revision = "20260622_000019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alpha_analysis_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=True),
        sa.Column("research_json", sa.Text(), nullable=True),
        sa.Column("trader_json", sa.Text(), nullable=True),
        sa.Column("risk_json", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alpha_analysis_runs")
