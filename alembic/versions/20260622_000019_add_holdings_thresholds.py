"""Add stop loss and take profit ratios to alpha holdings entries.

Revision ID: 20260622_000019
Revises: 20260621_000018
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa

revision = "20260622_000019"
down_revision = "20260621_000018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alpha_holdings_entries",
        sa.Column(
            "stop_loss_ratio",
            sa.Float(),
            nullable=False,
            server_default="-0.08",
        ),
    )
    op.add_column(
        "alpha_holdings_entries",
        sa.Column(
            "take_profit_ratio",
            sa.Float(),
            nullable=False,
            server_default="0.20",
        ),
    )


def downgrade() -> None:
    op.drop_column("alpha_holdings_entries", "take_profit_ratio")
    op.drop_column("alpha_holdings_entries", "stop_loss_ratio")
