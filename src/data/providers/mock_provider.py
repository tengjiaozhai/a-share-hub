import random
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
from src.data.providers.base import DataProvider, MarketSnapshot


class MockProvider(DataProvider):
    """模拟数据提供者，用于测试和开发"""

    def __init__(self, available: bool = True):
        self._available = available

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        """获取模拟实时行情"""
        if not self._available:
            return None

        base_price = random.uniform(10.0, 100.0)
        return MarketSnapshot(
            symbol=symbol,
            timestamp=datetime.now(),
            open=base_price * random.uniform(0.98, 1.0),
            high=base_price * random.uniform(1.0, 1.05),
            low=base_price * random.uniform(0.95, 1.0),
            close=base_price,
            volume=random.randint(1000, 1000000),
            amount=random.uniform(10000, 10000000),
            bid_price=base_price * 0.999,
            bid_volume=random.randint(100, 10000),
            ask_price=base_price * 1.001,
            ask_volume=random.randint(100, 10000),
        )

    def get_history(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        freq: str = "daily"
    ) -> pd.DataFrame:
        """获取模拟历史数据"""
        if not self._available:
            return pd.DataFrame()

        dates = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # 跳过周末
                dates.append(current)
            current += timedelta(days=1)

        data = []
        base_price = random.uniform(10.0, 100.0)
        for date in dates:
            open_price = base_price * random.uniform(0.98, 1.02)
            close_price = open_price * random.uniform(0.95, 1.05)
            data.append({
                "date": date,
                "open": open_price,
                "high": max(open_price, close_price) * random.uniform(1.0, 1.03),
                "low": min(open_price, close_price) * random.uniform(0.97, 1.0),
                "close": close_price,
                "volume": random.randint(100000, 10000000),
                "amount": random.uniform(1000000, 100000000),
            })
            base_price = close_price

        return pd.DataFrame(data)

    def get_stock_list(self) -> pd.DataFrame:
        """获取模拟股票列表"""
        if not self._available:
            return pd.DataFrame()

        stocks = [
            {"symbol": "000001.SZ", "name": "平安银行", "industry": "银行"},
            {"symbol": "600000.SH", "name": "浦发银行", "industry": "银行"},
            {"symbol": "000002.SZ", "name": "万科A", "industry": "房地产"},
            {"symbol": "600036.SH", "name": "招商银行", "industry": "银行"},
            {"symbol": "000858.SZ", "name": "五粮液", "industry": "白酒"},
        ]
        return pd.DataFrame(stocks)

    def is_available(self) -> bool:
        """检查模拟数据源是否可用"""
        return self._available
