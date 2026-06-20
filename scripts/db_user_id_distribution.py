"""统计 user_id 值的分布，看是否有 system 之外的值。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from src.core.config import Settings

settings = Settings()
dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(dsn, autocommit=True)
cur = conn.cursor()

TABLES_WITH_USER_ID = [
    "a_share_watchlist", "us_watchlist", "alpha_watchlist_items",
    "user_preferences", "decision_runs", "decision_input_snapshots",
    "target_positions", "execution_orders", "account_snapshots",
    "alpha_tickets", "dashboard_run_events", "paper_runs",
    "paper_accounts", "paper_nav_daily",
]

print(f"{'table':<32} {'user_id':<24} {'count':<10}")
print("-" * 70)
for table in TABLES_WITH_USER_ID:
    cur.execute(
        f"SELECT user_id, COUNT(*) FROM {table} "
        f"GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 5"
    )
    rows = cur.fetchall()
    if not rows:
        continue
    for i, (uid, cnt) in enumerate(rows):
        marker = " ← non-system" if uid not in ("system", None) else ""
        print(f"{table if i == 0 else '':<32} {str(uid):<24} {cnt:<10}{marker}")
conn.close()
