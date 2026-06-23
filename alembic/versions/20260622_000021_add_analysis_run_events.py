"""Add alpha analysis run events and lifecycle columns.

Revision ID: 20260622_000021
Revises: 20260622_000020
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "20260622_000021"
down_revision = "20260622_000020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alpha_analysis_runs",
        sa.Column(
            "current_stage",
            sa.String(length=32),
            nullable=False,
            server_default="accepted",
        ),
    )
    op.add_column(
        "alpha_analysis_runs",
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "alpha_analysis_runs",
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "alpha_analysis_runs",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "alpha_analysis_runs",
        sa.Column("backtest_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "alpha_analysis_run_events",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "payload_json",
            sa.Text(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_alpha_analysis_run_events_user_id",
        "alpha_analysis_run_events",
        ["user_id"],
    )
    op.create_index(
        "ix_alpha_analysis_run_events_run_id",
        "alpha_analysis_run_events",
        ["run_id"],
    )
    op.create_unique_constraint(
        "uq_alpha_run_events_run_seq",
        "alpha_analysis_run_events",
        ["run_id", "seq"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_alpha_run_events_run_seq", "alpha_analysis_run_events", type_="unique")
    op.drop_index("ix_alpha_analysis_run_events_run_id", table_name="alpha_analysis_run_events")
    op.drop_index("ix_alpha_analysis_run_events_user_id", table_name="alpha_analysis_run_events")
    op.drop_table("alpha_analysis_run_events")
    op.drop_column("alpha_analysis_runs", "backtest_json")
    op.drop_column("alpha_analysis_runs", "updated_at")
    op.drop_column("alpha_analysis_runs", "finished_at")
    op.drop_column("alpha_analysis_runs", "started_at")
    op.drop_column("alpha_analysis_runs", "current_stage")
