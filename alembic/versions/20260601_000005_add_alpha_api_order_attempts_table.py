from alembic import op
import sqlalchemy as sa


revision = "20260601_000005"
down_revision = "20260601_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alpha_api_order_attempts",
        sa.Column("attempt_id", sa.String(length=64), primary_key=True),
        sa.Column("ticket_id", sa.String(length=64), nullable=False),
        sa.Column("asset_symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remote_order_id", sa.String(length=64), nullable=True),
        sa.Column("response_payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alpha_api_order_attempts")
