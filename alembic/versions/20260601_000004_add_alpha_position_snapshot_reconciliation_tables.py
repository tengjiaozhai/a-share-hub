from alembic import op
import sqlalchemy as sa


revision = "20260601_000004"
down_revision = "20260524_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alpha_positions",
        sa.Column("symbol", sa.String(length=32), primary_key=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "alpha_portfolio_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True),
        sa.Column("cash_balance", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("nav", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "alpha_reconciliation_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("discrepancies_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alpha_reconciliation_runs")
    op.drop_table("alpha_portfolio_snapshots")
    op.drop_table("alpha_positions")
