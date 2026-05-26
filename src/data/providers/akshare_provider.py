import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from src.data.providers.base import DataProvider, MarketSnapshot

logger = logging.getLogger(__name__)


class AkshareProvider(DataProvider):
    """AkShare 行情数据提供者（免费，无需 token）"""

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        """获取单股实时行情，symbol 格式如 600519.SH / 000001.SZ"""
        try:
            import akshare as ak
            code, _ = _split(symbol)
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if row.empty:
                logger.warning(f"AkshareProvider: 未找到 {symbol}")
                return None
            r = row.iloc[0]
            last_price = _to_float(r.get("最新价"), default=0.0) or 0.0
            open_price = _to_float(r.get("今开"), default=last_price) or last_price
            high_price = _to_float(r.get("最高"), default=last_price) or last_price
            low_price = _to_float(r.get("最低"), default=last_price) or last_price
            return MarketSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                open=open_price,
                high=high_price,
                low=low_price,
                close=last_price,
                volume=_to_int(r.get("成交量"), default=0) or 0,
                amount=_to_float(r.get("成交额"), default=0.0) or 0.0,
                bid_price=_to_float(r.get("买一"), default=None),
                bid_volume=_to_int(r.get("买一量"), default=None),
                ask_price=_to_float(r.get("卖一"), default=None),
                ask_volume=_to_int(r.get("卖一量"), default=None),
            )
        except Exception as e:
            logger.warning(f"AkshareProvider.get_realtime_quote({symbol}) 失败: {e}")
            return None

    def get_history(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        freq: str = "daily",
    ) -> pd.DataFrame:
        """获取历史 K 线数据"""
        try:
            import akshare as ak
            code, _ = _split(symbol)
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "涨跌幅": "change_pct",
            })
            return df
        except Exception as e:
            logger.warning(f"AkshareProvider.get_history({symbol}) 失败: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            df = df.rename(columns={"code": "symbol", "name": "name"})
            return df
        except Exception as e:
            logger.warning(f"AkshareProvider.get_stock_list 失败: {e}")
            return pd.DataFrame()

    def is_available(self) -> bool:
        try:
            import akshare  # noqa: F401
            return True
        except ImportError:
            return False


def _split(symbol: str) -> tuple[str, str]:
    """600519.SH -> ('600519', 'SH')"""
    parts = symbol.split(".")
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _to_float(value, default: float | None) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value):
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
