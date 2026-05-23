import pytest
from datetime import datetime, timedelta
from src.data.providers.base import DataProvider, MarketSnapshot
from src.data.providers.mock_provider import MockProvider
from src.data.providers.provider_chain import ProviderChain


class UnavailableProvider(DataProvider):
    """不可用的数据提供者，用于测试故障转移"""
    
    def get_realtime_quote(self, symbol: str):
        return None
    
    def get_history(self, symbol, start_date, end_date, freq="daily"):
        return None
    
    def get_stock_list(self):
        return None
    
    def is_available(self):
        return False


class FailingProvider(DataProvider):
    """会抛出异常的数据提供者，用于测试异常处理"""
    
    def get_realtime_quote(self, symbol: str):
        raise RuntimeError("模拟异常")
    
    def get_history(self, symbol, start_date, end_date, freq="daily"):
        raise RuntimeError("模拟异常")
    
    def get_stock_list(self):
        raise RuntimeError("模拟异常")
    
    def is_available(self):
        return True


class TestProviderChain:
    def test_empty_providers_raises_error(self):
        """测试空提供者列表抛出异常"""
        with pytest.raises(ValueError, match="至少需要一个数据提供者"):
            ProviderChain([])
    
    def test_single_provider(self):
        """测试单个提供者"""
        mock_provider = MockProvider()
        chain = ProviderChain([mock_provider])
        
        snapshot = chain.get_realtime_quote("000001.SZ")
        assert snapshot is not None
        assert snapshot.symbol == "000001.SZ"
    
    def test_fallback_to_available_provider(self):
        """测试故障转移到可用提供者"""
        unavailable_provider = UnavailableProvider()
        mock_provider = MockProvider()
        chain = ProviderChain([unavailable_provider, mock_provider])
        
        snapshot = chain.get_realtime_quote("000001.SZ")
        assert snapshot is not None
    
    def test_exception_handling(self):
        """测试异常处理"""
        failing_provider = FailingProvider()
        mock_provider = MockProvider()
        chain = ProviderChain([failing_provider, mock_provider])
        
        snapshot = chain.get_realtime_quote("000001.SZ")
        assert snapshot is not None
    
    def test_all_providers_unavailable(self):
        """测试所有提供者不可用"""
        unavailable1 = UnavailableProvider()
        unavailable2 = UnavailableProvider()
        chain = ProviderChain([unavailable1, unavailable2])
        
        snapshot = chain.get_realtime_quote("000001.SZ")
        assert snapshot is None
    
    def test_get_history(self):
        """测试获取历史数据"""
        mock_provider = MockProvider()
        chain = ProviderChain([mock_provider])
        
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        history = chain.get_history("000001.SZ", start_date, end_date)
        
        assert not history.empty
        assert "date" in history.columns
        assert "open" in history.columns
        assert "close" in history.columns
    
    def test_get_stock_list(self):
        """测试获取股票列表"""
        mock_provider = MockProvider()
        chain = ProviderChain([mock_provider])
        
        stock_list = chain.get_stock_list()
        
        assert not stock_list.empty
        assert "symbol" in stock_list.columns
        assert "name" in stock_list.columns
    
    def test_is_available(self):
        """测试检查可用性"""
        mock_provider = MockProvider()
        chain = ProviderChain([mock_provider])
        
        assert chain.is_available() is True
    
    def test_add_provider(self):
        """测试添加提供者"""
        mock_provider1 = MockProvider()
        mock_provider2 = MockProvider()
        chain = ProviderChain([mock_provider1])
        
        chain.add_provider(mock_provider2)
        assert len(chain._providers) == 2
    
    def test_add_provider_at_index(self):
        """测试在指定位置添加提供者"""
        mock_provider1 = MockProvider()
        mock_provider2 = MockProvider()
        mock_provider3 = MockProvider()
        chain = ProviderChain([mock_provider1, mock_provider3])
        
        chain.add_provider(mock_provider2, index=1)
        assert len(chain._providers) == 3
        assert isinstance(chain._providers[1], MockProvider)
    
    def test_remove_provider(self):
        """测试移除提供者"""
        mock_provider = MockProvider()
        unavailable_provider = UnavailableProvider()
        chain = ProviderChain([mock_provider, unavailable_provider])
        
        chain.remove_provider(UnavailableProvider)
        assert len(chain._providers) == 1
        assert isinstance(chain._providers[0], MockProvider)
