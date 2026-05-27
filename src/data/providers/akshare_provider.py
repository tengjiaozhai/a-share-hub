import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from src.data.providers.akshare_catalog import StockCatalogCache, normalize_symbol
from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_snapshot_cache import SpotSnapshotCache
from src.data.providers.base import DataProvider, MarketSnapshot

logger = logging.getLogger(__name__)

# 腾讯行情字段索引（~ 分隔，0-indexed）
_TX_IDX = {
    "name": 1,
    "close": 3,   # 最新价
    "prev_close": 4,
    "open": 5,
    "volume": 6,  # 成交量（手）
    "amount": 37, # 成交额（元）
    "high": 33,
    "low": 34,
}

_TX_EXCHANGE_MAP = {"SH": "sh", "SZ": "sz", "BJ": "bj"}


def _fetch_tencent_quotes(symbols: list[str]) -> pd.DataFrame:
    """批量拉腾讯行情，symbols 格式 ['600519.SH', '000858.SZ']。
    
    返回含 code/symbol/最新价/今开/最高/最低/成交量/成交额 列的 DataFrame。
    """
    codes = []
    symbol_map = {}  # tx_code -> normalized_symbol
    for sym in symbols:
        parts = sym.split(".")
        if len(parts) != 2:
            continue
        code, ex = parts[0], parts[1].upper()
        tx_prefix = _TX_EXCHANGE_MAP.get(ex, "sh")
        tx_code = f"{tx_prefix}{code}"
        codes.append(tx_code)
        symbol_map[tx_code] = sym

    if not codes:
        return pd.DataFrame()

    url = f"https://qt.gtimg.cn/q={','.join(codes)}"
    resp = requests.get(url, timeout=8)
    resp.raise_for_status()

    rows = []
    for line in resp.text.strip().split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        tx_code_part = line.split("=")[0].replace("v_", "").strip()
        value_part = line.split("=", 1)[1].strip().strip('"').strip("'")
        fields = value_part.split("~")
        if len(fields) < 38:
            continue
        sym = symbol_map.get(tx_code_part)
        if not sym:
            continue
        code = sym.split(".")[0]
        rows.append({
            "code": code,
            "symbol": sym,
            "最新价": fields[_TX_IDX["close"]],
            "今开": fields[_TX_IDX["open"]],
            "最高": fields[_TX_IDX["high"]],
            "最低": fields[_TX_IDX["low"]],
            "成交量": fields[_TX_IDX["volume"]],
            "成交额": fields[_TX_IDX["amount"]],
        })

    return pd.DataFrame(rows)


def _build_catalog_frame() -> pd.DataFrame:
    """从腾讯行情接口拉全市场行情，构造 code/name DataFrame 供 StockCatalogCache 使用。
    
    腾讯没有列表接口，用 infer_exchange 支持的代码范围推断，
    实际 catalog 仅用于搜索，quote 路径不依赖它做校验。
    """
    # 返回空 DataFrame，catalog 暂不提供完整列表
    # quote 路径直接走腾讯接口，靠返回空数据识别无效 symbol
    return pd.DataFrame(columns=["code", "name"])


class AkshareProvider(DataProvider):
    """AkShare 行情数据提供者。

    股票列表：akshare stock_a_code_to_symbol（本地映射，无需网络）
    行情快照：腾讯 qt.gtimg.cn（可穿透当前代理）
    历史 K 线：暂缓（东方财富和新浪均不可达）
    """

    def __init__(
        self,
        catalog: StockCatalogCache | None = None,
        snapshot_cache: SpotSnapshotCache | None = None,
    ):
        self._catalog = catalog or StockCatalogCache()
        # 每个 symbol 独立一个缓存实例，TTL 15 分钟
        self._snapshot_caches: dict[str, SpotSnapshotCache] = {}
        self._snapshot_ttl = 900

    def _get_snapshot_cache(self, code: str) -> SpotSnapshotCache:
        if code not in self._snapshot_caches:
            self._snapshot_caches[code] = SpotSnapshotCache(ttl_seconds=self._snapshot_ttl)
        return self._snapshot_caches[code]

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        """先做 symbol 格式校验，再从腾讯行情取快照。
        
        格式非法（无法推断交易所）→ KeyError
        腾讯接口失败 → AkshareUpstreamError
        腾讯返回空（symbol 不存在）→ KeyError
        """
        try:
            normalized = normalize_symbol(symbol)
        except ValueError:
            raise KeyError(symbol)

        # 用 symbol 直接打腾讯接口，单 symbol 独立缓存
        code = normalized.split(".")[0]
        row = self._get_snapshot_cache(code).get_row(
            code,
            lambda: _fetch_tencent_quotes([normalized]),
        )

        last_price = _to_float(row.get("最新价"), 0.0) or 0.0
        open_price = _to_float(row.get("今开"), last_price) or last_price
        high_price = _to_float(row.get("最高"), last_price) or last_price
        low_price = _to_float(row.get("最低"), last_price) or last_price

        return MarketSnapshot(
            symbol=normalized,
            timestamp=datetime.now(),
            open=open_price,
            high=high_price,
            low=low_price,
            close=last_price,
            volume=_to_int(row.get("成交量"), 0) or 0,
            amount=_to_float(row.get("成交额"), 0.0) or 0.0,
        )

    def get_history(self, symbol: str, start_date: datetime, end_date: datetime, freq: str = "daily") -> pd.DataFrame:
        """历史 K 线暂不可用（eastmoney 被封）。"""
        logger.warning(f"get_history({symbol}) 暂不可用：eastmoney 接口被代理拦截")
        return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        return self._catalog.load(_build_catalog_frame)

    def is_available(self) -> bool:
        try:
            import akshare  # noqa: F401
            return True
        except ImportError:
            return False

def _to_float(value, default: float | None) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()) or (hasattr(pd, 'isna') and pd.isna(value)):
        return default
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int | None) -> int | None:
    numeric = _to_float(value, default=None)
    if numeric is None:
        return default
    try:
        return int(numeric)
    except (TypeError, ValueError):
        return default
