"""导入全部 A 股到 a_share_watchlist 表，热门股票优先排在前面。

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

# 热门股票（优先排在前面）
HOT_STOCKS = [
    "600519.SH", "000858.SZ", "601318.SH", "000001.SZ", "600036.SH",
    "000333.SZ", "002594.SZ", "601899.SH", "600900.SH", "600276.SH",
    "000568.SZ", "002304.SZ", "601398.SH", "601288.SH", "600030.SH",
    "601166.SH", "000002.SZ", "600000.SH", "601012.SH", "600887.SH",
    "000651.SZ", "002415.SZ", "600031.SH", "601088.SH", "600585.SH",
    "002475.SZ", "300750.SZ", "600809.SH", "002714.SZ", "600050.SH",
    "601668.SH", "600048.SH", "002352.SZ", "600104.SH", "601857.SH",
    "600028.SH", "601390.SH", "601669.SH", "002230.SZ", "300059.SZ",
    "002049.SZ", "600745.SH", "002456.SZ", "300433.SZ", "002241.SZ",
    "600588.SH", "002236.SZ", "300124.SZ", "600570.SH", "300015.SZ",
    # 半导体/芯片
    "688981.SH", "688008.SH", "002371.SZ", "300661.SZ", "300782.SZ",
    "603986.SH", "688135.SH", "002049.SZ", "688012.SH", "688036.SH",
    "688120.SH", "688256.SH", "688396.SH", "688521.SH", "688536.SH",
    # 新能源
    "300274.SZ", "600438.SH", "601012.SH", "002129.SZ", "300316.SZ",
    # 消费
    "600887.SH", "000568.SZ", "002304.SZ", "600809.SH", "000858.SZ",
    # 医药
    "600276.SH", "300015.SZ", "000538.SZ", "600196.SH", "002007.SZ",
    # 金融
    "601398.SH", "601288.SH", "600030.SH", "601166.SH", "601318.SH",
    # 军工
    "600893.SH", "000768.SZ", "600760.SH", "601989.SH", "600150.SH",
]


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
    all_stocks = frame[["symbol", "name"]].values.tolist()
    print(f"共获取 {len(all_stocks)} 只 A 股")

    # 重新排序：热门股票优先
    hot_set = set(HOT_STOCKS)
    hot_list = []
    other_list = []

    # 先从 all_stocks 中找热门股票
    stock_dict = {s[0]: s[1] for s in all_stocks}
    for sym in HOT_STOCKS:
        if sym in stock_dict:
            hot_list.append((sym, stock_dict[sym]))

    # 再添加其余股票
    for sym, name in all_stocks:
        if sym not in hot_set:
            other_list.append((sym, name))

    ordered_stocks = hot_list + other_list
    print(f"热门股票: {len(hot_list)} 只, 其他: {len(other_list)} 只")

    from src.storage.connection_url import build_psycopg_dsn

    conn_url = build_psycopg_dsn(database_url)
    conn = psycopg.connect(conn_url, row_factory=psycopg.rows.dict_row)

    # 清空旧数据（仅清空 system 用户的）
    with conn.cursor() as cur:
        cur.execute("DELETE FROM a_share_watchlist WHERE user_id = 'system'")
    conn.commit()
    print("已清空旧数据")

    # 批量插入
    inserted = 0
    batch_size = 500

    for i in range(0, len(ordered_stocks), batch_size):
        batch = ordered_stocks[i:i + batch_size]
        values = [("system", s[0], str(s[1]).strip(), i + j) for j, s in enumerate(batch)]

        try:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO a_share_watchlist (user_id, symbol, name, sort_order) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (user_id, symbol) DO NOTHING",
                    values,
                )
                inserted += cur.rowcount
            conn.commit()
        except Exception as e:
            print(f"Error in batch {i}: {e}")
            conn.rollback()

        print(f"  进度: {min(i + batch_size, len(ordered_stocks))}/{len(ordered_stocks)}")

    conn.close()
    print(f"完成: inserted={inserted}, total={len(ordered_stocks)}")


if __name__ == "__main__":
    main()
