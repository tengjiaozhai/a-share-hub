"""导入全部 A 股到 a_share_watchlist 表。

用法:
    /opt/anaconda3/envs/py311/bin/python3 scripts/init_a_share_watchlist.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env 文件
from pathlib import Path
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

import psycopg
from src.data.providers.akshare_provider import AkshareProvider


def main():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    # 获取全部 A 股
    provider = AkshareProvider()
    if not provider.is_available():
        print("ERROR: akshare provider unavailable")
        return

    print("正在获取全部 A 股列表...")
    frame = provider.get_stock_list()
    stocks = frame[["symbol", "name"]].values.tolist()
    print(f"共获取 {len(stocks)} 只 A 股")

    conn_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    conn = psycopg.connect(conn_url, row_factory=psycopg.rows.dict_row)

    # 批量插入
    inserted = 0
    skipped = 0
    batch_size = 500

    for i in range(0, len(stocks), batch_size):
        batch = stocks[i:i + batch_size]
        values = [(s[0], str(s[1]).strip(), i + j) for j, s in enumerate(batch)]

        try:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO a_share_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
                    "ON CONFLICT (symbol) DO NOTHING",
                    values,
                )
                inserted += cur.rowcount
                skipped += len(batch) - cur.rowcount
            conn.commit()
        except Exception as e:
            print(f"Error in batch {i}: {e}")
            conn.rollback()

        print(f"  进度: {min(i + batch_size, len(stocks))}/{len(stocks)}")

    conn.close()
    print(f"完成: inserted={inserted}, skipped={skipped}, total={len(stocks)}")


if __name__ == "__main__":
    main()
