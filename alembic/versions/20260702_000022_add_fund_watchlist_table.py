"""Add fund watchlist table.

Revision ID: 20260702_000022
Revises: 20260622_000021
Create Date: 2026-07-02
"""

import sqlalchemy as sa

from alembic import op

revision = "20260702_000022"
down_revision = "20260622_000021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "fund_watchlist" not in tables:
        op.create_table(
            "fund_watchlist",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("symbol", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "symbol", name="uq_fund_watchlist_user_symbol"),
        )

    index_names = {idx["name"] for idx in inspector.get_indexes("fund_watchlist")}
    if "ix_fund_watchlist_user_id" not in index_names:
        op.create_index("ix_fund_watchlist_user_id", "fund_watchlist", ["user_id"], unique=False)
    if "ix_fund_watchlist_symbol" not in index_names:
        op.create_index("ix_fund_watchlist_symbol", "fund_watchlist", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fund_watchlist_symbol", table_name="fund_watchlist")
    op.drop_index("ix_fund_watchlist_user_id", table_name="fund_watchlist")
    op.drop_table("fund_watchlist")
