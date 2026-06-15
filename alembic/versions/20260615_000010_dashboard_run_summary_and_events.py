from alembic import op
import sqlalchemy as sa


revision = "20260615_000010"
down_revision = "20260607_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_run_summaries",
        sa.Column("run_context_id", sa.String(length=64), primary_key=True),
        sa.Column("trade_date", sa.String(length=10), nullable=False),
        sa.Column("decision_mode", sa.String(length=16), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("capital_base", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("execution_fee_total", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("net_pnl", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("latest_workbench_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "dashboard_run_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("run_context_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_dashboard_run_events_run_context_seq",
        "dashboard_run_events",
        ["run_context_id", "seq"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_run_events_run_context_seq", table_name="dashboard_run_events")
    op.drop_table("dashboard_run_events")
    op.drop_table("dashboard_run_summaries")
