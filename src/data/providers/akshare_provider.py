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
            code, market = _split(symbol)
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code]
            if row.empty:
                logger.warning(f"AkshareProvider: 未找到 {symbol}")
                return None
            r = row.iloc[0]
            return MarketSnapshot(
                symbol=symbol,
                name=str(r.get("名称", "")),
                price=float(r.get("最新价", 0) or 0),
                change_pct=float(r.get("涨跌幅", 0) or 0),
                volume=float(r.get("成交量", 0) or 0),
                timestamp=datetime.now(),
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
