"""导入 A 股热门股票到 a_share_watchlist 表。

用法:
    /opt/anaconda3/envs/py311/bin/python3 scripts/init_a_share_watchlist.py
"""

import os
import psycopg

HOT_STOCKS = [
    ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"), ("601318.SH", "中国平安"),
    ("000001.SZ", "平安银行"), ("600036.SH", "招商银行"), ("000333.SZ", "美的集团"),
    ("002594.SZ", "比亚迪"), ("601899.SH", "紫金矿业"), ("600900.SH", "长江电力"),
    ("600276.SH", "恒瑞医药"), ("000568.SZ", "泸州老窖"), ("002304.SZ", "洋河股份"),
    ("601398.SH", "工商银行"), ("601288.SH", "农业银行"), ("600030.SH", "中信证券"),
    ("601166.SH", "兴业银行"), ("000002.SZ", "万科A"), ("600000.SH", "浦发银行"),
    ("601012.SH", "隆基绿能"), ("600887.SH", "伊利股份"), ("000651.SZ", "格力电器"),
    ("002415.SZ", "海康威视"), ("600031.SH", "三一重工"), ("601088.SH", "中国神华"),
    ("600585.SH", "海螺水泥"), ("002475.SZ", "立讯精密"), ("300750.SZ", "宁德时代"),
    ("600809.SH", "山西汾酒"), ("002714.SZ", "牧原股份"), ("600050.SH", "中国联通"),
    ("601668.SH", "中国建筑"), ("600048.SH", "保利发展"), ("002352.SZ", "顺丰控股"),
    ("600104.SH", "上汽集团"), ("601857.SH", "中国石油"), ("600028.SH", "中国石化"),
    ("601390.SH", "中国中铁"), ("601669.SH", "中国电建"), ("002230.SZ", "科大讯飞"),
    ("300059.SZ", "东方财富"), ("002049.SZ", "紫光国微"), ("600745.SH", "闻泰科技"),
    ("002456.SZ", "欧菲光"), ("300433.SZ", "蓝思科技"), ("002241.SZ", "歌尔股份"),
    ("600588.SH", "用友网络"), ("002236.SZ", "大华股份"), ("300124.SZ", "汇川技术"),
    ("600570.SH", "恒生电子"), ("300015.SZ", "爱尔眼科"),
]


def main():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    conn = psycopg.connect(conn_url, row_factory=psycopg.rows.dict_row)
    inserted = 0
    skipped = 0

    for i, (symbol, name) in enumerate(HOT_STOCKS):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO a_share_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
                    "ON CONFLICT (symbol) DO NOTHING",
                    (symbol, name, i),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        except Exception as e:
            print(f"Error inserting {symbol}: {e}")
            conn.rollback()

    conn.commit()
    conn.close()
    print(f"Done: inserted={inserted}, skipped={skipped}, total={len(HOT_STOCKS)}")


if __name__ == "__main__":
    main()