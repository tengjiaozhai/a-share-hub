"""扫描所有 user_id 列，找出 NULL 数据并报告。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from src.core.config import Settings

settings = Settings()
dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(dsn, autocommit=True)
cur = conn.cursor()

# 所有应该被修复为 system 的表（迁移中加了 user_id 列）
TABLES_WITH_USER_ID = [
    "a_share_watchlist",
    "us_watchlist",
    "alpha_watchlist_items",
    "user_preferences",
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
    "paper_runs",
    "paper_positions",
    "paper_fills",
    "paper_accounts",
    "paper_nav_daily",
]

print(f"Database: {dsn.split('@')[-1] if '@' in dsn else dsn}\n")
print(f"{'table':<32} {'has_user_id':<12} {'null_count':<12} {'total':<10}")
print("-" * 70)

nulls_by_table = {}
total_nulls = 0

for table in TABLES_WITH_USER_ID:
    try:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s AND column_name='user_id'",
            (table,),
        )
        has_col = cur.fetchone() is not None
        if not has_col:
            print(f"{table:<32} {'NO':<12} {'-':<12} {'-':<10}")
            continue
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL OR user_id = ''")
        null_count = cur.fetchone()[0]
        marker = " ← NEED FIX" if null_count > 0 else ""
        print(f"{table:<32} {'YES':<12} {null_count:<12} {total:<10}{marker}")
        if null_count > 0:
            nulls_by_table[table] = null_count
            total_nulls += null_count
    except Exception as e:
        print(f"{table:<32} ERROR: {e}")

print("-" * 70)
print(f"Total NULL user_id rows: {total_nulls}")
print(f"Tables needing fix: {list(nulls_by_table.keys())}")
conn.close()
