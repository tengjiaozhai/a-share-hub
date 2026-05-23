from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
import pandas as pd
from pydantic import BaseModel


class MarketSnapshot(BaseModel):
    """市场快照数据"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    bid_price: Optional[float] = None
    bid_volume: Optional[int] = None
    ask_price: Optional[float] = None
    ask_volume: Optional[int] = None


class DataProvider(ABC):
    """数据提供者基类"""
    
    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        """获取实时行情快照"""
        pass
    
    @abstractmethod
    def get_history(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        freq: str = "daily"
    ) -> pd.DataFrame:
        """获取历史数据"""
        pass
    
    @abstractmethod
    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass
