"""Add alpha analysis performance indexes.

Revision ID: 20260624_000021
Revises: 20260622_000021
Create Date: 2026-06-24
"""

from alembic import op

revision = "20260624_000021"
down_revision = "20260622_000021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_alpha_runs_user_status_created",
        "alpha_analysis_runs",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "ix_alpha_runs_user_symbol_status",
        "alpha_analysis_runs",
        ["user_id", "symbol", "status"],
    )
    op.create_index(
        "ix_alpha_run_events_run_seq",
        "alpha_analysis_run_events",
        ["run_id", "seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_alpha_run_events_run_seq", table_name="alpha_analysis_run_events")
    op.drop_index("ix_alpha_runs_user_symbol_status", table_name="alpha_analysis_runs")
    op.drop_index("ix_alpha_runs_user_status_created", table_name="alpha_analysis_runs")
