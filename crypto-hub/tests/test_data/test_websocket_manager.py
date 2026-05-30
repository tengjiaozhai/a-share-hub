import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.data.websocket_manager import WebSocketManager


@pytest.fixture
def manager():
    return WebSocketManager(testnet=True)


def test_manager_initialization(manager):
    """测试管理器初始化"""
    assert manager.testnet is True
    assert "testnet" in manager.ws_url
    assert manager.connections == {}
    assert manager.callbacks == {}


@pytest.mark.asyncio
async def test_subscribe(manager):
    """测试订阅"""
    callback = AsyncMock()

    with patch.object(manager, "connect", new_callable=AsyncMock) as mock_connect:
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        await manager.subscribe("btcusdt@ticker", callback)

        assert "btcusdt@ticker" in manager.callbacks
        assert callback in manager.callbacks["btcusdt@ticker"]
        mock_connect.assert_called_once_with("btcusdt@ticker")


@pytest.mark.asyncio
async def test_unsubscribe(manager):
    """测试取消订阅"""
    callback = AsyncMock()
    manager.callbacks["btcusdt@ticker"] = [callback]
    manager.connections["btcusdt@ticker"] = AsyncMock()

    with patch.object(manager, "disconnect", new_callable=AsyncMock) as mock_disconnect:
        await manager.unsubscribe("btcusdt@ticker")

        assert "btcusdt@ticker" not in manager.callbacks
        mock_disconnect.assert_called_once_with("btcusdt@ticker")


@pytest.mark.asyncio
async def test_subscribe_ticker(manager):
    """测试订阅实时价格"""
    callback = AsyncMock()

    with patch.object(manager, "subscribe", new_callable=AsyncMock) as mock_subscribe:
        await manager.subscribe_ticker("BTCUSDT", callback)
        mock_subscribe.assert_called_once_with("btcusdt@ticker", callback)


@pytest.mark.asyncio
async def test_subscribe_kline(manager):
    """测试订阅K线数据"""
    callback = AsyncMock()

    with patch.object(manager, "subscribe", new_callable=AsyncMock) as mock_subscribe:
        await manager.subscribe_kline("BTCUSDT", "1h", callback)
        mock_subscribe.assert_called_once_with("btcusdt@kline_1h", callback)


@pytest.mark.asyncio
async def test_subscribe_depth(manager):
    """测试订阅深度数据"""
    callback = AsyncMock()

    with patch.object(manager, "subscribe", new_callable=AsyncMock) as mock_subscribe:
        await manager.subscribe_depth("BTCUSDT", callback)
        mock_subscribe.assert_called_once_with("btcusdt@depth", callback)


def test_manager_initialization_mainnet():
    """测试主网初始化"""
    manager = WebSocketManager(testnet=False)
    assert manager.testnet is False
    assert "stream.binance.com" in manager.ws_url


@pytest.mark.asyncio
async def test_handle_message(manager):
    """测试消息处理"""
    callback = AsyncMock()
    manager.callbacks["btcusdt@ticker"] = [callback]

    message = '{"symbol": "BTCUSDT", "price": "50000"}'
    await manager._handle_message("btcusdt@ticker", message)

    callback.assert_called_once_with({"symbol": "BTCUSDT", "price": "50000"})
