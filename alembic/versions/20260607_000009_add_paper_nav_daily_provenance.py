from alembic import op
import sqlalchemy as sa


revision = "20260607_000009"
down_revision = "20260606_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_nav_daily",
        sa.Column("run_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "paper_nav_daily",
        sa.Column("source", sa.String(16), nullable=False, server_default="auto"),
    )


def downgrade() -> None:
    op.drop_column("paper_nav_daily", "source")
    op.drop_column("paper_nav_daily", "run_id")
