import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from src.data.data_cache import DataCache


@pytest.fixture
def cache():
    return DataCache(redis_url="redis://localhost:6379/1")


@pytest.mark.asyncio
async def test_cache_initialization(cache):
    """测试缓存初始化"""
    assert cache.redis is not None
    assert cache.default_ttl is not None


@pytest.mark.asyncio
async def test_get_set(cache):
    """测试获取和设置缓存"""
    test_data = {"price": "42000.00", "symbol": "BTCUSDT"}
    
    with patch.object(cache.redis, 'setex', new_callable=AsyncMock) as mock_set:
        with patch.object(cache.redis, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = '{"price": "42000.00", "symbol": "BTCUSDT"}'.encode()
            
            await cache.set("test_key", test_data)
            result = await cache.get("test_key")
            
            assert result == test_data
            mock_set.assert_called_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_empty(cache):
    """测试缓存为空时返回None"""
    with patch.object(cache.redis, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        
        result = await cache.get("nonexistent_key")
        assert result is None


@pytest.mark.asyncio
async def test_delete(cache):
    """测试删除缓存"""
    with patch.object(cache.redis, 'delete', new_callable=AsyncMock) as mock_delete:
        await cache.delete("test_key")
        mock_delete.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_exists(cache):
    """测试检查缓存是否存在"""
    with patch.object(cache.redis, 'exists', new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = 1
        result = await cache.exists("test_key")
        assert result is True
        
        mock_exists.return_value = 0
        result = await cache.exists("test_key")
        assert result is False


@pytest.mark.asyncio
async def test_make_key(cache):
    """测试生成缓存键"""
    key = cache._make_key("ticker", "BTCUSDT")
    assert key == "crypto:ticker:BTCUSDT"
    
    key = cache._make_key("klines", "BTCUSDT", "1h")
    assert key == "crypto:klines:BTCUSDT:1h"


@pytest.mark.asyncio
async def test_get_ticker(cache):
    """测试获取ticker缓存"""
    test_data = {"symbol": "BTCUSDT", "price": "42000.00"}
    
    with patch.object(cache, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = test_data
        
        result = await cache.get_ticker("BTCUSDT")
        assert result == test_data
        mock_get.assert_called_once_with("crypto:ticker:BTCUSDT")


@pytest.mark.asyncio
async def test_set_ticker(cache):
    """测试设置ticker缓存"""
    test_data = {"symbol": "BTCUSDT", "price": "42000.00"}
    
    with patch.object(cache, 'set', new_callable=AsyncMock) as mock_set:
        await cache.set_ticker("BTCUSDT", test_data)
        mock_set.assert_called_once_with("crypto:ticker:BTCUSDT", test_data, ttl=timedelta(seconds=30))


@pytest.mark.asyncio
async def test_get_klines(cache):
    """测试获取K线缓存"""
    test_data = [[1234567890, "42000", "43000", "41000", "42500", "100"]]
    
    with patch.object(cache, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = test_data
        
        result = await cache.get_klines("BTCUSDT", "1h")
        assert result == test_data
        mock_get.assert_called_once_with("crypto:klines:BTCUSDT:1h")


@pytest.mark.asyncio
async def test_set_klines(cache):
    """测试设置K线缓存"""
    test_data = [[1234567890, "42000", "43000", "41000", "42500", "100"]]
    
    with patch.object(cache, 'set', new_callable=AsyncMock) as mock_set:
        await cache.set_klines("BTCUSDT", "1h", test_data)
        mock_set.assert_called_once_with("crypto:klines:BTCUSDT:1h", test_data, ttl=timedelta(minutes=5))


@pytest.mark.asyncio
async def test_get_order_book(cache):
    """测试获取订单簿缓存"""
    test_data = {"bids": [["42000", "1"]], "asks": [["42100", "2"]]}
    
    with patch.object(cache, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = test_data
        
        result = await cache.get_order_book("BTCUSDT")
        assert result == test_data
        mock_get.assert_called_once_with("crypto:orderbook:BTCUSDT")


@pytest.mark.asyncio
async def test_set_order_book(cache):
    """测试设置订单簿缓存"""
    test_data = {"bids": [["42000", "1"]], "asks": [["42100", "2"]]}
    
    with patch.object(cache, 'set', new_callable=AsyncMock) as mock_set:
        await cache.set_order_book("BTCUSDT", test_data)
        mock_set.assert_called_once_with("crypto:orderbook:BTCUSDT", test_data, ttl=timedelta(seconds=10))


@pytest.mark.asyncio
async def test_close(cache):
    """测试关闭连接"""
    with patch.object(cache.redis, 'close', new_callable=AsyncMock) as mock_close:
        await cache.close()
        mock_close.assert_called_once()
