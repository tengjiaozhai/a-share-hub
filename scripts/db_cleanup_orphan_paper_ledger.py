"""清理孤儿 user_id 的 paper_ledger 数据。

孤儿定义：user_id 不在 app_users 表里。

修复方式：DELETE 这些行（基于用户决定）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from src.core.config import Settings

settings = Settings()
dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(dsn, autocommit=False)
cur = conn.cursor()

PAPER_LEDGER_TABLES = [
    "paper_accounts",
    "paper_runs",
    "paper_positions",
    "paper_fills",
    "paper_nav_daily",
]

# 查找孤儿 user_id（在 paper_ledger 里有，但在 app_users 里没有）
print("=== 查找孤儿 user_id ===")
all_orphans = set()
for table in PAPER_LEDGER_TABLES:
    cur.execute(
        f"SELECT DISTINCT user_id FROM {table} "
        f"WHERE user_id != 'system' AND user_id NOT IN (SELECT user_id FROM app_users)"
    )
    orphans = [r[0] for r in cur.fetchall()]
    if orphans:
        print(f"  {table}: {orphans}")
        all_orphans.update(orphans)

if not all_orphans:
    print("  (no orphans)")
    conn.close()
    sys.exit(0)

print(f"\n=== 将删除 user_id in {sorted(all_orphans)} ===")

# 按依赖顺序删除：先删除从属表，最后删 paper_accounts
DELETE_ORDER = [
    "paper_nav_daily",
    "paper_fills",
    "paper_positions",
    "paper_runs",
    "paper_accounts",
]

total_deleted = 0
for table in DELETE_ORDER:
    cur.execute(
        f"DELETE FROM {table} WHERE user_id = ANY(%s)",
        (list(all_orphans),)
    )
    deleted = cur.rowcount
    print(f"  {table}: deleted {deleted} rows")
    total_deleted += deleted

conn.commit()
print(f"\n=== Total deleted: {total_deleted} rows ===")
conn.close()
