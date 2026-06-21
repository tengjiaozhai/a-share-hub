"""Add alpha holdings entries table.

Revision ID: 20260621_000018
Revises: 20260620_000017
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa

revision = "20260621_000018"
down_revision = "20260620_000017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alpha_holdings_entries",
        sa.Column("entry_id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("buy_date", sa.String(length=32), nullable=False),
        sa.Column("buy_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alpha_holdings_entries")
