from alembic import op
import sqlalchemy as sa


revision = "20260602_000006"
down_revision = "20260601_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "us_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_us_watchlist_symbol", "us_watchlist", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_us_watchlist_symbol", table_name="us_watchlist")
    op.drop_table("us_watchlist")