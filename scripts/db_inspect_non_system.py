"""检查 paper_accounts 的非 system 用户行。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from src.core.config import Settings

settings = Settings()
dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(dsn, autocommit=True)
cur = conn.cursor()

print("=== paper_accounts non-system rows ===")
cur.execute(
    "SELECT account_id, user_id, market, initial_capital, created_at "
    "FROM paper_accounts WHERE user_id != 'system' ORDER BY created_at"
)
for r in cur.fetchall():
    print(r)

print("\n=== app_users (real users) ===")
cur.execute("SELECT user_id, username, email, role, disabled, created_at, last_login_at FROM app_users")
for r in cur.fetchall():
    print(r)

print("\n=== paper_runs per user ===")
cur.execute(
    "SELECT user_id, market, run_source, COUNT(*) FROM paper_runs GROUP BY user_id, market, run_source ORDER BY user_id"
)
for r in cur.fetchall():
    print(r)

print("\n=== paper_nav_daily per user ===")
cur.execute(
    "SELECT user_id, account_id, trade_date, nav FROM paper_nav_daily ORDER BY user_id, trade_date LIMIT 5"
)
for r in cur.fetchall():
    print(r)

print("\n=== a_share_watchlist sample (top 10) ===")
cur.execute("SELECT user_id, symbol, name FROM a_share_watchlist LIMIT 10")
for r in cur.fetchall():
    print(r)

conn.close()
