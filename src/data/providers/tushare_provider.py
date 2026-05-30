import logging
from datetime import datetime
from typing import Optional
import pandas as pd
from src.data.providers.base import DataProvider, MarketSnapshot

logger = logging.getLogger(__name__)

class TushareProvider(DataProvider):
    def __init__(self, token: str = "") -> None:
        self._token = token
        self._pro = None

    def _get_pro(self):
        if self._pro is None and self._token:
            try:
                import tushare as ts
                ts.set_token(self._token)
                self._pro = ts.pro_api()
            except Exception as e:
                logger.error(f"Tushare 初始化失败: {e}")
        return self._pro

    def is_available(self) -> bool:
        return bool(self._token) and self._get_pro() is not None

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        pro = self._get_pro()
        if pro is None:
            return None
        try:
            df = pro.daily(ts_code=_to_ts_code(symbol), limit=1)
            if df.empty:
                return None
            r = df.iloc[0]
            return MarketSnapshot(
                symbol=symbol,
                timestamp=datetime.strptime(str(r["trade_date"]), "%Y%m%d"),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=int(r["vol"]),
                amount=float(r["amount"]) * 1000,
            )
        except Exception as e:
            logger.warning(f"Tushare get_realtime_quote({symbol}) 失败: {e}")
            return None

    def get_history(self, symbol: str, start_date: datetime, end_date: datetime, freq: str = "daily") -> pd.DataFrame:
        pro = self._get_pro()
        if pro is None:
            return pd.DataFrame()
        try:
            df = pro.daily(ts_code=_to_ts_code(symbol), start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"))
            return df.rename(columns={"trade_date": "date", "vol": "volume"}) if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning(f"Tushare get_history({symbol}) 失败: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        pro = self._get_pro()
        if pro is None:
            return pd.DataFrame()
        try:
            df = pro.stock_list(exchange="", list_status="L")
            return df.rename(columns={"ts_code": "symbol"})[["symbol", "name"]] if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning(f"Tushare get_stock_list 失败: {e}")
            return pd.DataFrame()

def _to_ts_code(symbol: str) -> str:
    return symbol.upper()
