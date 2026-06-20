import sqlalchemy as sa
from alembic import op


revision = "20260620_000015"
down_revision = "20260620_000014"
branch_labels = None
depends_on = None


_PAPER_TABLES = [
    "paper_runs",
    "paper_positions",
    "paper_fills",
]


def _column_exists(inspector, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def _index_exists(inspector, table: str, index_name: str) -> bool:
    try:
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table))
    except Exception:
        return False


def _column_has_default(inspector, table: str, column: str) -> bool:
    try:
        for c in inspector.get_columns(table):
            if c["name"] == column:
                return c.get("default") is not None
    except Exception:
        return False
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # 1) 单 PK 表加 user_id 列 + 索引（幂等）
    for table in _PAPER_TABLES:
        if not _column_exists(inspector, table, "user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "user_id",
                        sa.String(length=64),
                        nullable=False,
                        server_default="system",
                    )
                )
        if not _index_exists(inspector, table, f"ix_{table}_user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.create_index(f"ix_{table}_user_id", ["user_id"], unique=False)
        if not is_sqlite and _column_has_default(inspector, table, "user_id"):
            op.alter_column(table, "user_id", server_default=None)

    # 2) paper_accounts: UniqueConstraint 升级为 (user_id, market, account_kind)
    _upgrade_paper_accounts(inspector, is_sqlite)

    # 3) paper_nav_daily: UniqueConstraint 升级为 (user_id, account_id, trade_date, source)
    _upgrade_paper_nav_daily(inspector, is_sqlite)


def _upgrade_paper_accounts(inspector, is_sqlite: bool) -> None:
    """paper_accounts: UniqueConstraint 升级为 (user_id, market, account_kind) — 幂等。"""
    # 如果 user_id 列已存在且复合唯一约束已建立，跳过
    if _column_exists(inspector, "paper_accounts", "user_id") and _index_exists(
        inspector, "paper_accounts", "uq_paper_accounts_user_market_kind"
    ):
        return

    # 用 IF EXISTS 幂等删除老约束/索引（无论是否存在都安全）
    op.execute("ALTER TABLE paper_accounts DROP CONSTRAINT IF EXISTS paper_accounts_market_account_kind_key")
    op.execute("DROP INDEX IF EXISTS uq_paper_accounts_market_kind")
    op.execute("DROP INDEX IF EXISTS ix_paper_accounts_market_kind")

    if not _column_exists(inspector, "paper_accounts", "user_id"):
        with op.batch_alter_table("paper_accounts") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "user_id",
                    sa.String(length=64),
                    nullable=False,
                    server_default="system",
                )
            )
    if not is_sqlite and _column_has_default(inspector, "paper_accounts", "user_id"):
        op.alter_column("paper_accounts", "user_id", server_default=None)

    if not _index_exists(inspector, "paper_accounts", "uq_paper_accounts_user_market_kind"):
        op.create_index(
            "uq_paper_accounts_user_market_kind",
            "paper_accounts",
            ["user_id", "market", "account_kind"],
            unique=True,
        )
    if not _index_exists(inspector, "paper_accounts", "ix_paper_accounts_user_id"):
        op.create_index("ix_paper_accounts_user_id", "paper_accounts", ["user_id"])


def _upgrade_paper_nav_daily(inspector, is_sqlite: bool) -> None:
    """paper_nav_daily: UniqueConstraint 升级为 (user_id, account_id, trade_date, source) — 幂等。"""
    if _column_exists(inspector, "paper_nav_daily", "user_id") and _index_exists(
        inspector, "paper_nav_daily", "uq_paper_nav_daily_user_account_date_source"
    ):
        return

    op.execute("ALTER TABLE paper_nav_daily DROP CONSTRAINT IF EXISTS paper_nav_daily_account_id_trade_date_source_key")
    op.execute("DROP INDEX IF EXISTS uq_paper_nav_daily_account_date_source")

    if not _column_exists(inspector, "paper_nav_daily", "user_id"):
        with op.batch_alter_table("paper_nav_daily") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "user_id",
                    sa.String(length=64),
                    nullable=False,
                    server_default="system",
                )
            )
    if not is_sqlite and _column_has_default(inspector, "paper_nav_daily", "user_id"):
        op.alter_column("paper_nav_daily", "user_id", server_default=None)

    if not _index_exists(inspector, "paper_nav_daily", "uq_paper_nav_daily_user_account_date_source"):
        op.create_index(
            "uq_paper_nav_daily_user_account_date_source",
            "paper_nav_daily",
            ["user_id", "account_id", "trade_date", "source"],
            unique=True,
        )
    if not _index_exists(inspector, "paper_nav_daily", "ix_paper_nav_daily_user_id"):
        op.create_index("ix_paper_nav_daily_user_id", "paper_nav_daily", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, "paper_nav_daily", "uq_paper_nav_daily_user_account_date_source"):
        op.drop_index("uq_paper_nav_daily_user_account_date_source", table_name="paper_nav_daily")
    if not _index_exists(inspector, "paper_nav_daily", "uq_paper_nav_daily_account_date_source"):
        op.create_index(
            "uq_paper_nav_daily_account_date_source",
            "paper_nav_daily",
            ["account_id", "trade_date", "source"],
            unique=True,
        )
    if _index_exists(inspector, "paper_nav_daily", "ix_paper_nav_daily_user_id"):
        op.drop_index("ix_paper_nav_daily_user_id", table_name="paper_nav_daily")
    if _column_exists(inspector, "paper_nav_daily", "user_id"):
        with op.batch_alter_table("paper_nav_daily") as batch_op:
            batch_op.drop_column("user_id")

    if _index_exists(inspector, "paper_accounts", "uq_paper_accounts_user_market_kind"):
        op.drop_index("uq_paper_accounts_user_market_kind", table_name="paper_accounts")
    if not _index_exists(inspector, "paper_accounts", "uq_paper_accounts_market_kind"):
        op.create_index(
            "uq_paper_accounts_market_kind",
            "paper_accounts",
            ["market", "account_kind"],
            unique=True,
        )
    if _index_exists(inspector, "paper_accounts", "ix_paper_accounts_user_id"):
        op.drop_index("ix_paper_accounts_user_id", table_name="paper_accounts")
    if _column_exists(inspector, "paper_accounts", "user_id"):
        with op.batch_alter_table("paper_accounts") as batch_op:
            batch_op.drop_column("user_id")

    for table in _PAPER_TABLES:
        if _index_exists(inspector, table, f"ix_{table}_user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_index(f"ix_{table}_user_id")
        if _column_exists(inspector, table, "user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("user_id")
