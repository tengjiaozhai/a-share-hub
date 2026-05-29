from fastapi import APIRouter, HTTPException, Query

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_provider import AkshareProvider

router = APIRouter(prefix="/api/v1/market")

_akshare_provider: AkshareProvider | None = None


def _get_akshare_provider() -> AkshareProvider:
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AkshareProvider()
    return _akshare_provider


@router.get("/stocks")
def list_market_stocks(
    query: str = Query("", max_length=50),
    exchange: str = Query("all"),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    frame = provider.get_stock_list()
    records = frame.copy()
    exchange_upper = exchange.strip().upper()
    if exchange_upper and exchange_upper != "ALL":
        records = records[records["exchange"] == exchange_upper]
    q = query.strip()
    if q:
        records = records[
            records["symbol"].str.contains(q, case=False, na=False)
            | records["code"].str.contains(q, case=False, na=False)
            | records["name"].str.contains(q, case=False, na=False)
        ]
    return records.head(limit).to_dict("records")


# 美股知名股票列表（使用 Stooq 符号）
_US_STOCKS_LIST = [
    {"symbol": "AAPL.US", "name": "苹果", "stooq_symbol": "aapl.us"},
    {"symbol": "MSFT.US", "name": "微软", "stooq_symbol": "msft.us"},
    {"symbol": "GOOGL.US", "name": "谷歌", "stooq_symbol": "googl.us"},
    {"symbol": "AMZN.US", "name": "亚马逊", "stooq_symbol": "amzn.us"},
    {"symbol": "NVDA.US", "name": "英伟达", "stooq_symbol": "nvda.us"},
    {"symbol": "TSLA.US", "name": "特斯拉", "stooq_symbol": "tsla.us"},
    {"symbol": "META.US", "name": "Meta", "stooq_symbol": "meta.us"},
    {"symbol": "NFLX.US", "name": "奈飞", "stooq_symbol": "nflx.us"},
    {"symbol": "AMD.US", "name": "超威半导体", "stooq_symbol": "amd.us"},
    {"symbol": "INTC.US", "name": "英特尔", "stooq_symbol": "intc.us"},
    {"symbol": "QCOM.US", "name": "高通", "stooq_symbol": "qcom.us"},
    {"symbol": "AVGO.US", "name": "博通", "stooq_symbol": "avgo.us"},
    {"symbol": "TXN.US", "name": "德州仪器", "stooq_symbol": "txn.us"},
    {"symbol": "ORCL.US", "name": "甲骨文", "stooq_symbol": "orcl.us"},
    {"symbol": "CRM.US", "name": "赛富时", "stooq_symbol": "crm.us"},
    {"symbol": "IBM.US", "name": "IBM国际商业机器", "stooq_symbol": "ibm.us"},
    {"symbol": "GS.US", "name": "高盛", "stooq_symbol": "gs.us"},
    {"symbol": "JPM.US", "name": "摩根大通", "stooq_symbol": "jpm.us"},
    {"symbol": "V.US", "name": "维萨", "stooq_symbol": "v.us"},
    {"symbol": "MA.US", "name": "万事达", "stooq_symbol": "ma.us"},
    {"symbol": "JNJ.US", "name": "强生", "stooq_symbol": "jnj.us"},
    {"symbol": "WMT.US", "name": "沃尔玛", "stooq_symbol": "wmt.us"},
    {"symbol": "DIS.US", "name": "迪士尼", "stooq_symbol": "dis.us"},
    {"symbol": "NKE.US", "name": "耐克", "stooq_symbol": "nke.us"},
    {"symbol": "MCD.US", "name": "麦当劳", "stooq_symbol": "mcd.us"},
    {"symbol": "KO.US", "name": "可口可乐", "stooq_symbol": "ko.us"},
    {"symbol": "PEP.US", "name": "百事", "stooq_symbol": "pep.us"},
    {"symbol": "PFE.US", "name": "辉瑞", "stooq_symbol": "pfe.us"},
    {"symbol": "BABA.US", "name": "阿里巴巴", "stooq_symbol": "baba.us"},
    {"symbol": "JD.US", "name": "京东", "stooq_symbol": "jd.us"},
]


# 美股指数列表
_US_INDICES = [
    {"symbol": "^NDQ", "name": "纳斯达克综合指数", "stooq_symbol": "^ndq"},
    {"symbol": "^SPX", "name": "标普500指数", "stooq_symbol": "^spx"},
    {"symbol": "^DJI", "name": "道琼斯工业指数", "stooq_symbol": "^dji"},
]


def _fetch_stooq_quote(session, stooq_symbol):
    """从 Stooq 获取股票/指数行情"""
    try:
        url = f"https://stooq.com/q/l/?s={stooq_symbol}&f=sd2t2ohlcv&h&e=csv"
        response = session.get(url, timeout=10)
        lines = response.text.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split(',')
            if len(parts) >= 8:
                close = float(parts[6]) if parts[6] else 0
                open_price = float(parts[3]) if parts[3] else 0
                change = close - open_price if open_price else 0
                change_pct = (change / open_price * 100) if open_price else 0
                return {
                    "close": close,
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "open": float(parts[3]) if parts[3] else 0,
                    "high": float(parts[4]) if parts[4] else 0,
                    "low": float(parts[5]) if parts[5] else 0,
                }
    except Exception:
        pass
    return None


@router.get("/stocks/us")
def list_us_stocks(
    query: str = Query("", max_length=50),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    """获取美股知名股票列表，支持搜索过滤。"""
    import requests
    import pandas as pd
    
    # 使用 Session 并禁用代理
    session = requests.Session()
    session.trust_env = False
    
    # 搜索过滤（先过滤，减少 API 调用次数）
    q = query.strip()
    
    # 1. 获取美股股票数据（从 Stooq）
    stocks_records = []
    for stock in _US_STOCKS_LIST:
        # 如果有搜索条件，先检查是否匹配
        if q:
            if not (q.lower() in stock["symbol"].lower() or q.lower() in stock["name"].lower()):
                continue
        
        quote = _fetch_stooq_quote(session, stock["stooq_symbol"])
        if quote:
            stocks_records.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "type": "stock",
                **quote,
            })
    
    # 2. 获取美股指数数据（从 Stooq）
    indices_records = []
    for index in _US_INDICES:
        # 如果有搜索条件，先检查是否匹配
        if q:
            if not (q.lower() in index["symbol"].lower() or q.lower() in index["name"].lower()):
                continue
        
        quote = _fetch_stooq_quote(session, index["stooq_symbol"])
        if quote:
            indices_records.append({
                "symbol": index["symbol"],
                "name": index["name"],
                "type": "index",
                **quote,
            })
    
    # 合并股票和指数
    all_records = stocks_records + indices_records
    df = pd.DataFrame(all_records)
    
    return df.head(limit).to_dict("records")
    
    # 搜索过滤
    q = query.strip()
    if q:
        df = df[
            df["symbol"].str.contains(q, case=False, na=False)
            | df["name"].str.contains(q, case=False, na=False)
        ]
    
    return df.head(limit).to_dict("records")


@router.get("/quote")
def get_market_quote(symbol: str = Query(..., min_length=3)) -> dict:
    normalized_symbol = symbol.strip().upper()
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    try:
        snapshot = provider.get_realtime_quote(normalized_symbol)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"quote symbol not found: {normalized_symbol}")
    except (AkshareUpstreamError, AkshareBreakerOpenError) as exc:
        raise HTTPException(status_code=503, detail=f"quote upstream unavailable: {exc}")
    return snapshot.model_dump()


@router.post("/bulk")
def get_bulk_quotes(symbols: list[str]) -> list[dict]:
    """批量获取行情，支持 200+ 只股票。"""
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    if not symbols:
        return []
    df = _fetch_tencent_quotes_batch(symbols[:500])
    if df.empty:
        return []
    return df.to_dict("records")
