import sqlalchemy as sa
from alembic import op


revision = "20260620_000014"
down_revision = "20260619_000012"
branch_labels = None
depends_on = None


# 15 张 user-owned 表，统一添加 user_id 列（默认 'system'，兼容旧数据）
# 注：AlphaPositionRow 和 DashboardRunSummaryRow 的主键从单字段升级为 (user_id, *) 复合主键
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

# 主键需要扩展的表：(原主键列) — 需要 ALTER PRIMARY KEY
# SQLite 不支持 ALTER PRIMARY KEY，需要 drop+recreate
_COMPOSITE_PK_TABLES = {
    "alpha_positions": "symbol",  # 新 PK: (user_id, symbol)
    "dashboard_run_summaries": "run_context_id",  # 新 PK: (user_id, run_context_id)
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    # 1) 为单 PK 表加 user_id 列 + 索引
    for table in _USER_TABLES:
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
        # PG: 把 server_default 拿掉，避免后续插入都靠默认值
        if not is_sqlite:
            op.alter_column(table, "user_id", server_default=None)

    # 2) 对需要复合主键的表（alpha_positions, dashboard_run_summaries）：
    #    SQLite 和 PG 都通过 drop+recreate 完成
    for table, old_pk in _COMPOSITE_PK_TABLES.items():
        if table == "alpha_positions":
            _recreate_alpha_positions(is_sqlite)
        elif table == "dashboard_run_summaries":
            _recreate_dashboard_run_summaries(is_sqlite)


def _recreate_alpha_positions(is_sqlite: bool) -> None:
    """alpha_positions: PK 改为 (user_id, symbol)"""
    if is_sqlite:
        # SQLite: rename + recreate + copy + drop old + rename
        with op.batch_alter_table("alpha_positions") as batch_op:
            batch_op.alter_column("user_id", new_column_name="user_id_legacy")
        op.execute(
            "ALTER TABLE alpha_positions RENAME TO _alpha_positions_old"
        )
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
    op.create_index("ix_alpha_positions_user_id", "alpha_positions", ["user_id"])


def _recreate_dashboard_run_summaries(is_sqlite: bool) -> None:
    """dashboard_run_summaries: PK 改为 (user_id, run_context_id)"""
    if is_sqlite:
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
    else:
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
    op.create_index("ix_dashboard_run_summaries_user_id", "dashboard_run_summaries", ["user_id"])


def downgrade() -> None:
    # 反向：先回滚复合 PK 表，再删除单 PK 表的 user_id 列
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 回滚 dashboard_run_summaries
    if is_sqlite:
        op.execute("ALTER TABLE dashboard_run_summaries RENAME TO _dashboard_run_summaries_new")
    else:
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

    # 回滚 alpha_positions
    if is_sqlite:
        op.execute("ALTER TABLE alpha_positions RENAME TO _alpha_positions_new")
    else:
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

    # 删除单 PK 表的 user_id 列
    for table in _USER_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_user_id")
            batch_op.drop_column("user_id")
