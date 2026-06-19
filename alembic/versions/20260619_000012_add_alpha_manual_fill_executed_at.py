import sqlalchemy as sa
from alembic import op


revision = "20260619_000012"
down_revision = "20260619_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alpha_manual_fills", sa.Column("executed_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE alpha_manual_fills SET executed_at = created_at WHERE executed_at IS NULL")
    op.alter_column("alpha_manual_fills", "executed_at", nullable=False)


def downgrade() -> None:
    op.drop_column("alpha_manual_fills", "executed_at")
