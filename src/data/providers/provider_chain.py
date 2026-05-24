from typing import List, Optional
from datetime import datetime
import logging
import pandas as pd
from src.data.providers.base import DataProvider, MarketSnapshot

logger = logging.getLogger(__name__)


class ProviderChain(DataProvider):
    """数据提供者链，按优先级尝试多个数据源"""
    
    def __init__(self, providers: List[DataProvider]):
        if not providers:
            raise ValueError("至少需要一个数据提供者")
        self._providers = providers
    
    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        """按优先级获取实时行情"""
        for provider in self._providers:
            try:
                if provider.is_available():
                    result = provider.get_realtime_quote(symbol)
                    if result is not None:
                        logger.debug(f"从 {type(provider).__name__} 获取到 {symbol} 的实时行情")
                        return result
            except Exception as e:
                logger.warning(f"{type(provider).__name__} 获取实时行情失败: {e}")
        
        logger.error(f"所有数据提供者都无法获取 {symbol} 的实时行情")
        return None
    
    def get_history(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime,
        freq: str = "daily"
    ) -> pd.DataFrame:
        """按优先级获取历史数据"""
        for provider in self._providers:
            try:
                if provider.is_available():
                    result = provider.get_history(symbol, start_date, end_date, freq)
                    if not result.empty:
                        logger.debug(f"从 {type(provider).__name__} 获取到 {symbol} 的历史数据")
                        return result
            except Exception as e:
                logger.warning(f"{type(provider).__name__} 获取历史数据失败: {e}")
        
        logger.error(f"所有数据提供者都无法获取 {symbol} 的历史数据")
        return pd.DataFrame()
    
    def get_stock_list(self) -> pd.DataFrame:
        """按优先级获取股票列表"""
        for provider in self._providers:
            try:
                if provider.is_available():
                    result = provider.get_stock_list()
                    if not result.empty:
                        logger.debug(f"从 {type(provider).__name__} 获取到股票列表")
                        return result
            except Exception as e:
                logger.warning(f"{type(provider).__name__} 获取股票列表失败: {e}")
        
        logger.error("所有数据提供者都无法获取股票列表")
        return pd.DataFrame()
    
    def is_available(self) -> bool:
        """检查是否有任何数据提供者可用"""
        return any(provider.is_available() for provider in self._providers)
    
    def add_provider(self, provider: DataProvider, index: Optional[int] = None):
        """添加数据提供者"""
        if index is None:
            self._providers.append(provider)
        else:
            self._providers.insert(index, provider)
        logger.info(f"添加数据提供者: {type(provider).__name__}")
    
    def remove_provider(self, provider_type: type):
        """移除指定类型的数据提供者"""
        self._providers = [p for p in self._providers if not isinstance(p, provider_type)]
        logger.info(f"移除数据提供者: {provider_type.__name__}")
