import sqlalchemy as sa
from alembic import op


revision = "20260620_000013"
down_revision = "20260619_000012"
branch_labels = None
depends_on = None


SYSTEM_USER_ID = "system"


def _index_exists(inspector, table: str, index_name: str) -> bool:
    """幂等检查：索引是否已存在。"""
    try:
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table))
    except Exception:
        return False


def _constraint_exists(inspector, table: str, constraint_name: str) -> bool:
    """幂等检查：约束是否已存在（unique / pk）。"""
    try:
        for uq in inspector.get_unique_constraints(table):
            if uq.get("name") == constraint_name:
                return True
        for pk in inspector.get_pk_constraint(table).get("constrained_columns", []):
            if pk == constraint_name:
                return True
        return False
    except Exception:
        return False


def _column_exists(inspector, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # a_share_watchlist
    if not _column_exists(inspector, "a_share_watchlist", "user_id"):
        op.add_column(
            "a_share_watchlist",
            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
                server_default=SYSTEM_USER_ID,
            ),
        )
    # 先删 unique constraint（顺带删 unique index），再尝试删非唯一索引
    op.execute("ALTER TABLE a_share_watchlist DROP CONSTRAINT IF EXISTS a_share_watchlist_symbol_key")
    op.execute("DROP INDEX IF EXISTS ix_a_share_watchlist_symbol")
    if not _index_exists(inspector, "a_share_watchlist", "ix_a_share_watchlist_user_id"):
        op.create_index(
            "ix_a_share_watchlist_user_id", "a_share_watchlist", ["user_id"], unique=False
        )
    if not _constraint_exists(inspector, "a_share_watchlist", "uq_a_share_watchlist_user_symbol"):
        op.create_unique_constraint(
            "uq_a_share_watchlist_user_symbol",
            "a_share_watchlist",
            ["user_id", "symbol"],
        )

    # us_watchlist
    if not _column_exists(inspector, "us_watchlist", "user_id"):
        op.add_column(
            "us_watchlist",
            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
                server_default=SYSTEM_USER_ID,
            ),
        )
    op.execute("ALTER TABLE us_watchlist DROP CONSTRAINT IF EXISTS us_watchlist_symbol_key")
    op.execute("DROP INDEX IF EXISTS ix_us_watchlist_symbol")
    if not _index_exists(inspector, "us_watchlist", "ix_us_watchlist_user_id"):
        op.create_index(
            "ix_us_watchlist_user_id", "us_watchlist", ["user_id"], unique=False
        )
    if not _constraint_exists(inspector, "us_watchlist", "uq_us_watchlist_user_symbol"):
        op.create_unique_constraint(
            "uq_us_watchlist_user_symbol",
            "us_watchlist",
            ["user_id", "symbol"],
        )

    # alpha_watchlist_items
    if not _column_exists(inspector, "alpha_watchlist_items", "user_id"):
        op.add_column(
            "alpha_watchlist_items",
            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
                server_default=SYSTEM_USER_ID,
            ),
        )
    if not _index_exists(inspector, "alpha_watchlist_items", "ix_alpha_watchlist_items_user_id"):
        op.create_index(
            "ix_alpha_watchlist_items_user_id",
            "alpha_watchlist_items",
            ["user_id"],
            unique=False,
        )
    if not _constraint_exists(inspector, "alpha_watchlist_items", "uq_alpha_watchlist_user_symbol"):
        op.create_unique_constraint(
            "uq_alpha_watchlist_user_symbol",
            "alpha_watchlist_items",
            ["user_id", "symbol"],
        )

    # user_preferences: 改主键为 (user_id, key)
    if not _column_exists(inspector, "user_preferences", "user_id"):
        op.add_column(
            "user_preferences",
            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
                server_default=SYSTEM_USER_ID,
            ),
        )
    # 主键重建（幂等）
    current_pk = inspector.get_pk_constraint("user_preferences").get("name")
    if current_pk == "user_preferences_pkey":
        # 检查列是否已包含 user_id
        pk_cols = inspector.get_pk_constraint("user_preferences").get("constrained_columns", [])
        if "user_id" not in pk_cols:
            op.drop_constraint("user_preferences_pkey", "user_preferences", type_="primary")
            op.create_primary_key(
                "user_preferences_pkey", "user_preferences", ["user_id", "key"]
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    current_pk = inspector.get_pk_constraint("user_preferences").get("name")
    if current_pk == "user_preferences_pkey":
        pk_cols = inspector.get_pk_constraint("user_preferences").get("constrained_columns", [])
        if "user_id" in pk_cols:
            op.drop_constraint("user_preferences_pkey", "user_preferences", type_="primary")
            op.create_primary_key("user_preferences_pkey", "user_preferences", ["key"])
    if _column_exists(inspector, "user_preferences", "user_id"):
        op.drop_column("user_preferences", "user_id")

    if _constraint_exists(inspector, "alpha_watchlist_items", "uq_alpha_watchlist_user_symbol"):
        op.drop_constraint(
            "uq_alpha_watchlist_user_symbol", "alpha_watchlist_items", type_="unique"
        )
    if _index_exists(inspector, "alpha_watchlist_items", "ix_alpha_watchlist_items_user_id"):
        op.drop_index("ix_alpha_watchlist_items_user_id", table_name="alpha_watchlist_items")
    if _column_exists(inspector, "alpha_watchlist_items", "user_id"):
        op.drop_column("alpha_watchlist_items", "user_id")

    if _constraint_exists(inspector, "us_watchlist", "uq_us_watchlist_user_symbol"):
        op.drop_constraint(
            "uq_us_watchlist_user_symbol", "us_watchlist", type_="unique"
        )
    if _index_exists(inspector, "us_watchlist", "ix_us_watchlist_user_id"):
        op.drop_index("ix_us_watchlist_user_id", table_name="us_watchlist")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_us_watchlist_symbol ON us_watchlist (symbol)")
    if _column_exists(inspector, "us_watchlist", "user_id"):
        op.drop_column("us_watchlist", "user_id")

    if _constraint_exists(inspector, "a_share_watchlist", "uq_a_share_watchlist_user_symbol"):
        op.drop_constraint(
            "uq_a_share_watchlist_user_symbol", "a_share_watchlist", type_="unique"
        )
    if _index_exists(inspector, "a_share_watchlist", "ix_a_share_watchlist_user_id"):
        op.drop_index("ix_a_share_watchlist_user_id", table_name="a_share_watchlist")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_a_share_watchlist_symbol ON a_share_watchlist (symbol)")
    if _column_exists(inspector, "a_share_watchlist", "user_id"):
        op.drop_column("a_share_watchlist", "user_id")
