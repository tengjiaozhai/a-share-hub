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
    "high": 33,
    "low": 34,
    "amount": 37, # 成交额（万元）
    "change_pct": 32,   # 涨跌幅 %
    "turnover": 38,      # 换手率 %
    "amplitude": 43,     # 振幅 %
    "volume_ratio": 49,  # 量比
    "pe_ratio": 39,      # 市盈率
}

_TX_EXCHANGE_MAP = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
_KLINE_FREQ_MAP = {"daily": "day", "weekly": "week", "monthly": "month"}


def _fetch_tencent_quotes(symbols: list[str]) -> pd.DataFrame:
    """批量拉腾讯行情，symbols 格式 ['600519.SH', '000858.SZ']。

    返回含 symbol/name/close/prev_close/open/high/low/volume/amount/change_pct/turnover/amplitude/volume_ratio/pe_ratio 列的 DataFrame。
    """
    codes = []
    symbol_map = {}
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
        if len(fields) < 50:
            continue
        sym = symbol_map.get(tx_code_part)
        if not sym:
            continue
        rows.append({
            "symbol": sym,
            "name": fields[_TX_IDX["name"]],
            "close": fields[_TX_IDX["close"]],
            "prev_close": fields[_TX_IDX["prev_close"]],
            "open": fields[_TX_IDX["open"]],
            "high": fields[_TX_IDX["high"]],
            "low": fields[_TX_IDX["low"]],
            "volume": fields[_TX_IDX["volume"]],
            "amount": fields[_TX_IDX["amount"]],
            "change_pct": fields[_TX_IDX["change_pct"]],
            "turnover": fields[_TX_IDX["turnover"]],
            "amplitude": fields[_TX_IDX["amplitude"]],
            "volume_ratio": fields[_TX_IDX["volume_ratio"]],
            "pe_ratio": fields[_TX_IDX["pe_ratio"]],
        })

    return pd.DataFrame(rows)


def _fetch_tencent_quotes_batch(symbols: list[str], batch_size: int = 200) -> pd.DataFrame:
    """分批拉取腾讯行情，支持全市场扫描。"""
    all_frames = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        df = _fetch_tencent_quotes(batch)
        if not df.empty:
            all_frames.append(df)
    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def _fetch_tencent_kline(tx_code: str, start_date: str, end_date: str, freq: str = "day") -> pd.DataFrame:
    """腾讯历史 K 线。

    tx_code: 腾讯格式代码，如 'sh600519'
    start_date / end_date: 'YYYY-MM-DD'
    freq: 'day' / 'week' / 'month'

    返回 columns: [date, open, close, high, low, volume]
    """
    try:
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={tx_code},{freq},{start_date},{end_date},1000,qfq"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return pd.DataFrame()

        stock_data = data.get("data", {})
        if not stock_data:
            return pd.DataFrame()

        kline_key = f"qfq{freq}"
        rows = []
        for key, val in stock_data.items():
            kline = val.get(kline_key, [])
            if not kline:
                continue
            for row in kline:
                if len(row) >= 6:
                    rows.append({
                        "date": row[0],
                        "open": float(row[1]),
                        "close": float(row[2]),
                        "high": float(row[3]),
                        "low": float(row[4]),
                        "volume": int(float(row[5])),
                    })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"_fetch_tencent_kline({tx_code}) 失败: {e}")
        return pd.DataFrame()


def _build_catalog_frame() -> pd.DataFrame:
    """从三大交易所官网获取全市场 A 股列表（不走东方财富）。"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return df[["code", "name"]]
    except Exception as e:
        logger.warning(f"_build_catalog_frame 失败: {e}")
        return pd.DataFrame(columns=["code", "name"])


class AkshareProvider(DataProvider):
    """AkShare 行情数据提供者。

    行情快照：腾讯 qt.gtimg.cn
    历史 K 线：腾讯 web.ifzq.gtimg.cn
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

        last_price = _to_float(row.get("close"), 0.0) or 0.0
        open_price = _to_float(row.get("open"), last_price) or last_price
        high_price = _to_float(row.get("high"), last_price) or last_price
        low_price = _to_float(row.get("low"), last_price) or last_price

        return MarketSnapshot(
            symbol=normalized,
            timestamp=datetime.now(),
            open=open_price,
            high=high_price,
            low=low_price,
            close=last_price,
            volume=_to_int(row.get("volume"), 0) or 0,
            amount=_to_float(row.get("amount"), 0.0) or 0.0,
        )

    def get_history(self, symbol: str, start_date: datetime, end_date: datetime, freq: str = "daily") -> pd.DataFrame:
        """获取历史 K 线数据（腾讯财经接口）。"""
        try:
            normalized = normalize_symbol(symbol)
        except ValueError:
            return pd.DataFrame()

        code, exchange = normalized.split(".")
        tx_code = f"{_TX_EXCHANGE_MAP.get(exchange, 'sh')}{code}"
        tx_freq = _KLINE_FREQ_MAP.get(freq, "day")
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        return _fetch_tencent_kline(tx_code, start_str, end_str, tx_freq)

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
