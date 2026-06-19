import sqlalchemy as sa
from alembic import op


revision = "20260619_000011"
down_revision = "20260615_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_paper_accounts_market_kind",
        "paper_accounts",
        ["market", "account_kind"],
        unique=True,
    )
    op.create_index(
        "uq_paper_nav_daily_account_date_source",
        "paper_nav_daily",
        ["account_id", "trade_date", "source"],
        unique=True,
    )
    op.create_table(
        "scheduled_job_locks",
        sa.Column("job_key", sa.String(length=128), primary_key=True),
        sa.Column("job_name", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("lock_owner", sa.String(length=128), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scheduled_job_locks")
    op.drop_index("uq_paper_nav_daily_account_date_source", table_name="paper_nav_daily")
    op.drop_index("uq_paper_accounts_market_kind", table_name="paper_accounts")
