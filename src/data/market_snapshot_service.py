from datetime import datetime
from typing import Optional, List
import pandas as pd
from loguru import logger
from src.data.providers.base import MarketSnapshot
from src.data.providers.provider_chain import ProviderChain


class MarketSnapshotService:
    """市场快照服务，提供统一的数据访问接口"""
    
    def __init__(self, provider_chain: ProviderChain):
        self._provider_chain = provider_chain
    
    def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """获取单个股票的实时快照"""
        return self._provider_chain.get_realtime_quote(symbol)
    
    def get_snapshots(self, symbols: List[str]) -> dict[str, Optional[MarketSnapshot]]:
        """获取多个股票的实时快照"""
        results = {}
        for symbol in symbols:
            results[symbol] = self._provider_chain.get_realtime_quote(symbol)
        return results
    
    def get_history(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        freq: str = "daily"
    ) -> pd.DataFrame:
        """获取历史数据"""
        return self._provider_chain.get_history(symbol, start_date, end_date, freq)
    
    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        return self._provider_chain.get_stock_list()
    
    def is_market_open(self) -> bool:
        """检查市场是否开盘"""
        now = datetime.now()
        return now.weekday() < 5 and (
            (now.hour == 9 and now.minute >= 30) or
            (10 <= now.hour <= 11) or
            (now.hour == 11 and now.minute <= 30) or
            (13 <= now.hour <= 14) or
            (now.hour == 15 and now.minute == 0)
        )
