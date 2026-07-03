"""Add composite indexes for /api/v1/dashboard/history performance.

Revision ID: 20260703_000023
Revises: 20260702_000022
Create Date: 2026-07-03
"""

import sqlalchemy as sa

from alembic import op

revision = "20260703_000023"
down_revision = "20260702_000022"
branch_labels = None
depends_on = None


_INDEXES = [
    # paper_runs: covers get_run_history (user_id + market + ordering by created_at)
    # and count_run_history (user_id + run_source + created_at for partial counts)
    ("paper_runs", "ix_paper_runs_user_market_created", ["user_id", "market", "created_at"]),
    ("paper_runs", "ix_paper_runs_user_source_created", ["user_id", "run_source", "created_at"]),
    # dashboard_run_summaries: covers list_dashboard_run_summaries
    ("dashboard_run_summaries", "ix_dash_sum_user_market_started", ["user_id", "market", "started_at"]),
    # decision_runs: covers get_dashboard_run_market fallback N+1
    ("decision_runs", "ix_decision_runs_user_ctx_created", ["user_id", "run_context_id", "created_at"]),
    # decision_input_snapshots: covers get_dashboard_run_market snapshot join
    ("decision_input_snapshots", "ix_decision_input_user_run", ["user_id", "decision_run_id"]),
    # target_positions: covers get_dashboard_run_market fallback N+1
    ("target_positions", "ix_target_pos_user_ctx_created", ["user_id", "run_context_id", "created_at"]),
    # execution_orders: covers get_dashboard_run_market fallback N+1
    ("execution_orders", "ix_exec_order_user_ctx_created", ["user_id", "run_context_id", "created_at"]),
]


def _index_exists(inspector, table: str, index_name: str) -> bool:
    try:
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table))
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table, idx_name, columns in _INDEXES:
        if table not in tables:
            continue
        if _index_exists(inspector, table, idx_name):
            continue
        op.create_index(idx_name, table, columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for table, idx_name, _ in reversed(_INDEXES):
        if table not in tables:
            continue
        if not _index_exists(inspector, table, idx_name):
            continue
        op.drop_index(idx_name, table_name=table)
