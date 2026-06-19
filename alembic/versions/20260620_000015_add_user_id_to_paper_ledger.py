import sqlalchemy as sa
from alembic import op


revision = "20260620_000015"
down_revision = "20260620_000014"
branch_labels = None
depends_on = None


# 5 张 paper_ledger 表，统一添加 user_id 列
# paper_accounts: UniqueConstraint 从 (market, account_kind) 升级为 (user_id, market, account_kind)
# paper_nav_daily: UniqueConstraint 从 (account_id, trade_date, source) 升级为 (user_id, account_id, trade_date, source)
_PAPER_TABLES = [
    "paper_runs",
    "paper_positions",
    "paper_fills",
]


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1) 单 PK 表加 user_id 列 + 索引
    for table in _PAPER_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "user_id",
                    sa.String(length=64),
                    nullable=False,
                    server_default="system",
                )
            )
            batch_op.create_index(f"ix_{table}_user_id", ["user_id"], unique=False)
        if not is_sqlite:
            op.alter_column(table, "user_id", server_default=None)

    # 2) paper_accounts: UniqueConstraint 升级
    _upgrade_paper_accounts(is_sqlite)

    # 3) paper_nav_daily: UniqueConstraint 升级
    _upgrade_paper_nav_daily(is_sqlite)


def _upgrade_paper_accounts(is_sqlite: bool) -> None:
    """paper_accounts: UniqueConstraint 升级为 (user_id, market, account_kind)"""
    op.execute("DROP INDEX IF EXISTS uq_paper_accounts_market_kind")
    op.execute("DROP INDEX IF EXISTS ix_paper_accounts_market_kind")
    op.execute("ALTER TABLE paper_accounts DROP CONSTRAINT IF EXISTS paper_accounts_market_account_kind_key")
    with op.batch_alter_table("paper_accounts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
                server_default="system",
            )
        )
    if not is_sqlite:
        op.alter_column("paper_accounts", "user_id", server_default=None)
    op.create_index(
        "uq_paper_accounts_user_market_kind",
        "paper_accounts",
        ["user_id", "market", "account_kind"],
        unique=True,
    )
    op.create_index("ix_paper_accounts_user_id", "paper_accounts", ["user_id"])


def _upgrade_paper_nav_daily(is_sqlite: bool) -> None:
    """paper_nav_daily: UniqueConstraint 升级为 (user_id, account_id, trade_date, source)"""
    op.execute("DROP INDEX IF EXISTS uq_paper_nav_daily_account_date_source")
    op.execute("ALTER TABLE paper_nav_daily DROP CONSTRAINT IF EXISTS paper_nav_daily_account_id_trade_date_source_key")
    with op.batch_alter_table("paper_nav_daily") as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
                server_default="system",
            )
        )
    if not is_sqlite:
        op.alter_column("paper_nav_daily", "user_id", server_default=None)
    op.create_index(
        "uq_paper_nav_daily_user_account_date_source",
        "paper_nav_daily",
        ["user_id", "account_id", "trade_date", "source"],
        unique=True,
    )
    op.create_index("ix_paper_nav_daily_user_id", "paper_nav_daily", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 反向：先回滚 unique，再删 user_id 列
    op.drop_index("uq_paper_nav_daily_user_account_date_source", table_name="paper_nav_daily")
    op.create_index(
        "uq_paper_nav_daily_account_date_source",
        "paper_nav_daily",
        ["account_id", "trade_date", "source"],
        unique=True,
    )
    with op.batch_alter_table("paper_nav_daily") as batch_op:
        batch_op.drop_index("ix_paper_nav_daily_user_id")
        batch_op.drop_column("user_id")

    op.drop_index("uq_paper_accounts_user_market_kind", table_name="paper_accounts")
    op.create_index(
        "uq_paper_accounts_market_kind",
        "paper_accounts",
        ["market", "account_kind"],
        unique=True,
    )
    with op.batch_alter_table("paper_accounts") as batch_op:
        batch_op.drop_index("ix_paper_accounts_user_id")
        batch_op.drop_column("user_id")

    for table in _PAPER_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_user_id")
            batch_op.drop_column("user_id")
