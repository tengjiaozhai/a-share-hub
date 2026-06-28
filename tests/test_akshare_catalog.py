import pandas as pd

from src.data.providers.akshare_catalog import (
    StockCatalogCache,
    infer_exchange,
    normalize_symbol,
    normalize_stock_list_frame,
)


def test_normalize_symbol_infers_exchange_from_code():
    assert normalize_symbol("000858") == "000858.SZ"
    assert normalize_symbol("600519") == "600519.SH"
    assert normalize_symbol("920001") == "920001.BJ"
    assert normalize_symbol("sz000858") == "000858.SZ"


def test_normalize_symbol_accepts_verified_fund_codes():
    assert normalize_symbol("512650") == "512650.SH"
    assert normalize_symbol("511280") == "511280.SH"
    assert normalize_symbol("159707") == "159707.SZ"
    assert normalize_symbol("166009") == "166009.SZ"


def test_normalize_stock_list_frame_adds_symbol_and_exchange():
    raw = pd.DataFrame(
        [
            {"code": "000858", "name": "五 粮 液"},
            {"code": "600519", "name": "贵州茅台"},
        ]
    )

    frame = normalize_stock_list_frame(raw)

    assert frame.to_dict("records") == [
        {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"},
        {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
    ]


def test_catalog_cache_filters_by_query_and_exchange():
    cache = StockCatalogCache(ttl_seconds=300)
    cache._frame = pd.DataFrame(
        [
            {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"},
            {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
            {"symbol": "920001.BJ", "code": "920001", "name": "纬达光电", "exchange": "BJ"},
        ]
    )

    records = cache.search(query="粮", exchange="SZ", limit=10)

    assert records == [
        {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"}
    ]
