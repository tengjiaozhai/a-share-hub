"""导入热门美股到 us_watchlist 表。

用法:
    /opt/anaconda3/envs/py311/bin/python3 scripts/init_us_watchlist.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

import psycopg
from src.storage.connection_url import build_psycopg_dsn

HOT_STOCKS = [
    # 科技巨头
    ("AAPL", "苹果"), ("MSFT", "微软"), ("GOOGL", "谷歌"), ("AMZN", "亚马逊"),
    ("NVDA", "英伟达"), ("TSLA", "特斯拉"), ("META", "Meta"), ("NFLX", "奈飞"),
    ("AMD", "超威半导体"), ("INTC", "英特尔"), ("QCOM", "高通"), ("AVGO", "博通"),
    ("TXN", "德州仪器"), ("ORCL", "甲骨文"), ("CRM", "赛富时"), ("IBM", "IBM"),
    ("ADBE", "奥多比"), ("CSCO", "思科"), ("NOW", "ServiceNow"), ("ACN", "埃森哲"),
    # 金融
    ("JPM", "摩根大通"), ("GS", "高盛"), ("V", "维萨"), ("MA", "万事达"),
    ("BAC", "美国银行"), ("WFC", "富国银行"), ("C", "花旗"), ("MS", "摩根士丹利"),
    ("AXP", "美国运通"), ("BLK", "贝莱德"), ("SCHW", "嘉信理财"), ("CB", "安达保险"),
    # 医疗健康
    ("JNJ", "强生"), ("UNH", "联合健康"), ("PFE", "辉瑞"), ("ABBV", "艾伯维"),
    ("MRK", "默沙东"), ("TMO", "赛默飞"), ("ABT", "雅培"), ("LLY", "礼来"),
    ("BMY", "百时美施贵宝"), ("AMGN", "安进"), ("GILD", "吉利德"), ("ISRG", "直觉外科"),
    # 消费
    ("WMT", "沃尔玛"), ("PG", "宝洁"), ("KO", "可口可乐"), ("PEP", "百事"),
    ("COST", "好市多"), ("NKE", "耐克"), ("MCD", "麦当劳"), ("DIS", "迪士尼"),
    ("SBUX", "星巴克"), ("TGT", "塔吉特"), ("LOW", "劳氏"), ("HD", "家得宝"),
    # 工业
    ("CAT", "卡特彼勒"), ("BA", "波明"), ("HON", "霍尼韦尔"), ("UPS", "联合包裹"),
    ("RTX", "雷神"), ("DE", "迪尔"), ("LMT", "洛克希德马丁"), ("GE", "通用电气"),
    # 能源
    ("XOM", "埃克森美孚"), ("CVX", "雪佛龙"), ("COP", "康菲石油"), ("SLB", "斯伦贝谢"),
    # 中概股
    ("BABA", "阿里巴巴"), ("JD", "京东"), ("PDD", "拼多多"), ("BIDU", "百度"),
    ("NIO", "蔚来"), ("XPEV", "小鹏"), ("LI", "理想"), ("NTES", "网易"),
    ("BILI", "哔哩哔哩"), ("TAL", "好未来"), ("EDU", "新东方"), ("IQ", "爱奇艺"),
    ("VIPS", "唯品会"), ("ZTO", "中通快递"), ("FUTU", "富途"),
    # 半导体
    ("TSM", "台积电"), ("ASML", "阿斯麦"), ("MU", "美光"),
    ("NXPI", "恩智浦"), ("MRVL", "美满电子"), ("ON", "安森美"), ("LRCX", "拉姆研究"),
    ("AMAT", "应用材料"), ("KLAC", "科磊"), ("SNPS", "新思科技"), ("CDNS", "铿腾电子"),
    # 云计算 / SaaS
    ("SNOW", "Snowflake"), ("PLTR", "Palantir"), ("DDOG", "Datadog"), ("NET", "Cloudflare"),
    ("ZS", "Zscaler"), ("CRWD", "CrowdStrike"), ("PANW", "Palo Alto"), ("OKTA", "Okta"),
    ("TEAM", "Atlassian"), ("TWLO", "Twilio"), ("SHOP", "Shopify"), ("SQ", "Block"),
    # ETF
    ("SPY", "标普500ETF"), ("QQQ", "纳斯达克100ETF"), ("DIA", "道指ETF"),
    ("IWM", "罗素2000ETF"), ("VTI", "全市场ETF"), ("VOO", "标普500ETF-Vanguard"),
    ("ARKK", "ARK创新ETF"), ("XLF", "金融ETF"), ("XLE", "能源ETF"), ("XLK", "科技ETF"),
    # 更多热门
    ("PLUG", "Plug Power"), ("SNAP", "Snap"), ("UBER", "Uber"), ("ABNB", "Airbnb"),
    ("COIN", "Coinbase"), ("HOOD", "Robinhood"), ("SOFI", "SoFi"), ("RIVN", "Rivian"),
    ("LCID", "Lucid"), ("ARM", "ARM"), ("SMCI", "超微电脑"), ("DELL", "戴尔"),
]


def main():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = psycopg.connect(build_psycopg_dsn(database_url), row_factory=psycopg.rows.dict_row)
    inserted = 0
    skipped = 0

    for i, (symbol, name) in enumerate(HOT_STOCKS):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO us_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
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
