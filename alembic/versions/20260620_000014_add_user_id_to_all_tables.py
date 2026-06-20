import sqlalchemy as sa
from alembic import op


revision = "20260620_000014"
down_revision = "20260620_000013"
branch_labels = None
depends_on = None


SYSTEM_USER_ID = "system"


# 13 张 user-owned 单 PK 表，统一添加 user_id 列
_USER_TABLES = [
    "execution_plans",
    "decision_runs",
    "decision_input_snapshots",
    "target_positions",
    "execution_orders",
    "risk_gate_events",
    "account_snapshots",
    "alpha_tickets",
    "alpha_manual_fills",
    "alpha_portfolio_snapshots",
    "alpha_reconciliation_runs",
    "alpha_api_order_attempts",
    "dashboard_run_events",
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
    """检查列是否仍有 server_default（幂等：第二次跑时不应再 alter_column 拿掉）。"""
    try:
        for c in inspector.get_columns(table):
            if c["name"] == column:
                # server_default 在 inspector 中是 dict，nullable 字段标识
                default = c.get("default")
                return default is not None
    except Exception:
        return False
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # 1) 为单 PK 表加 user_id 列 + 索引（幂等）
    for table in _USER_TABLES:
        if not _column_exists(inspector, table, "user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "user_id",
                        sa.String(length=64),
                        nullable=False,
                        server_default=SYSTEM_USER_ID,
                    )
                )
        if not _index_exists(inspector, table, f"ix_{table}_user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.create_index(f"ix_{table}_user_id", ["user_id"], unique=False)
        # PG: 把 server_default 拿掉（幂等：检查列是否仍有 default）
        if not is_sqlite and _column_has_default(inspector, table, "user_id"):
            op.alter_column(table, "user_id", server_default=None)

    # 2) 复合主键表：alpha_positions + dashboard_run_summaries
    #    通过 schema 检查避免重复 recreate
    _maybe_recreate_alpha_positions(inspector, is_sqlite)
    _maybe_recreate_dashboard_run_summaries(inspector, is_sqlite)


def _pk_columns(inspector, table: str) -> list[str]:
    try:
        return list(inspector.get_pk_constraint(table).get("constrained_columns", []))
    except Exception:
        return []


def _maybe_recreate_alpha_positions(inspector, is_sqlite: bool) -> None:
    """alpha_positions: PK 改为 (user_id, symbol) — 幂等。"""
    pk_cols = _pk_columns(inspector, "alpha_positions")
    if "user_id" in pk_cols:
        return  # 已是复合 PK，跳过
    if is_sqlite:
        with op.batch_alter_table("alpha_positions") as batch_op:
            batch_op.alter_column("user_id", new_column_name="user_id_legacy")
        op.execute("ALTER TABLE alpha_positions RENAME TO _alpha_positions_old")
    else:
        op.execute("ALTER TABLE alpha_positions RENAME TO _alpha_positions_old")
    op.create_table(
        "alpha_positions",
        sa.Column("symbol", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=64), primary_key=True, server_default="system"),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.Column("mark_price", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.execute(
        "INSERT INTO alpha_positions (symbol, user_id, quantity, avg_cost, mark_price, updated_at) "
        "SELECT symbol, 'system', quantity, avg_cost, mark_price, updated_at FROM _alpha_positions_old"
    )
    op.execute("DROP TABLE _alpha_positions_old")
    if not _index_exists(inspector, "alpha_positions", "ix_alpha_positions_user_id"):
        op.create_index("ix_alpha_positions_user_id", "alpha_positions", ["user_id"])


def _maybe_recreate_dashboard_run_summaries(inspector, is_sqlite: bool) -> None:
    """dashboard_run_summaries: PK 改为 (user_id, run_context_id) — 幂等。"""
    pk_cols = _pk_columns(inspector, "dashboard_run_summaries")
    if "user_id" in pk_cols:
        return  # 已是复合 PK，跳过
    op.execute("ALTER TABLE dashboard_run_summaries RENAME TO _dashboard_run_summaries_old")
    op.create_table(
        "dashboard_run_summaries",
        sa.Column("run_context_id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), primary_key=True, server_default="system"),
        sa.Column("trade_date", sa.String(length=10), nullable=False),
        sa.Column("decision_mode", sa.String(length=16), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("capital_base", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("execution_fee_total", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("net_pnl", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("latest_workbench_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    )
    op.execute(
        "INSERT INTO dashboard_run_summaries "
        "(run_context_id, user_id, trade_date, decision_mode, execution_mode, capital_base, status, "
        "execution_fee_total, realized_pnl, unrealized_pnl, net_pnl, started_at, finished_at, "
        "latest_workbench_json, created_at, updated_at) "
        "SELECT run_context_id, 'system', trade_date, decision_mode, execution_mode, capital_base, status, "
        "execution_fee_total, realized_pnl, unrealized_pnl, net_pnl, started_at, finished_at, "
        "latest_workbench_json, created_at, updated_at FROM _dashboard_run_summaries_old"
    )
    op.execute("DROP TABLE _dashboard_run_summaries_old")
    if not _index_exists(inspector, "dashboard_run_summaries", "ix_dashboard_run_summaries_user_id"):
        op.create_index("ix_dashboard_run_summaries_user_id", "dashboard_run_summaries", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # 反向：先回滚复合 PK 表，再删除单 PK 表的 user_id 列
    if "user_id" in _pk_columns(inspector, "dashboard_run_summaries"):
        op.execute("ALTER TABLE dashboard_run_summaries RENAME TO _dashboard_run_summaries_new")
        op.create_table(
            "dashboard_run_summaries",
            sa.Column("run_context_id", sa.String(length=64), primary_key=True),
            sa.Column("trade_date", sa.String(length=10), nullable=False),
            sa.Column("decision_mode", sa.String(length=16), nullable=False),
            sa.Column("execution_mode", sa.String(length=16), nullable=False),
            sa.Column("capital_base", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("execution_fee_total", sa.Float(), nullable=False),
            sa.Column("realized_pnl", sa.Float(), nullable=False),
            sa.Column("unrealized_pnl", sa.Float(), nullable=False),
            sa.Column("net_pnl", sa.Float(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("latest_workbench_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.execute(
            "INSERT INTO dashboard_run_summaries "
            "(run_context_id, trade_date, decision_mode, execution_mode, capital_base, status, "
            "execution_fee_total, realized_pnl, unrealized_pnl, net_pnl, started_at, finished_at, "
            "latest_workbench_json, created_at, updated_at) "
            "SELECT run_context_id, trade_date, decision_mode, execution_mode, capital_base, status, "
            "execution_fee_total, realized_pnl, unrealized_pnl, net_pnl, started_at, finished_at, "
            "latest_workbench_json, created_at, updated_at FROM _dashboard_run_summaries_new"
        )
        op.execute("DROP TABLE _dashboard_run_summaries_new")

    if "user_id" in _pk_columns(inspector, "alpha_positions"):
        op.execute("ALTER TABLE alpha_positions RENAME TO _alpha_positions_new")
        op.create_table(
            "alpha_positions",
            sa.Column("symbol", sa.String(length=32), primary_key=True),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("avg_cost", sa.Float(), nullable=False),
            sa.Column("mark_price", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.execute(
            "INSERT INTO alpha_positions (symbol, quantity, avg_cost, mark_price, updated_at) "
            "SELECT symbol, quantity, avg_cost, mark_price, updated_at FROM _alpha_positions_new"
        )
        op.execute("DROP TABLE _alpha_positions_new")

    for table in _USER_TABLES:
        if _index_exists(inspector, table, f"ix_{table}_user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_index(f"ix_{table}_user_id")
        if _column_exists(inspector, table, "user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("user_id")
