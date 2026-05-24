from alembic import op
import sqlalchemy as sa


revision = "20260524_000003"
down_revision = "20260524_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_orders",
        sa.Column("execution_order_id", sa.String(length=64), primary_key=True),
        sa.Column("target_position_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "risk_gate_events",
        sa.Column("risk_gate_event_id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("rule_name", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kill_switch_events",
        sa.Column("kill_switch_event_id", sa.String(length=64), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("kill_switch_events")
    op.drop_table("risk_gate_events")
    op.drop_table("execution_orders")
