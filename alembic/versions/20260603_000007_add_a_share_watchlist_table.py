from alembic import op
import sqlalchemy as sa


revision = "20260603_000007"
down_revision = "20260602_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "a_share_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_a_share_watchlist_symbol", "a_share_watchlist", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_a_share_watchlist_symbol", table_name="a_share_watchlist")
    op.drop_table("a_share_watchlist")
