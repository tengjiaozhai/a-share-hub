import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.execution.binance_client import BinanceClient
from src.core.enums import OrderSide, OrderType


@pytest.fixture
def client():
    return BinanceClient(
        api_key="test_api_key",
        api_secret="test_api_secret",
        testnet=True
    )


def test_client_initialization(client):
    """测试客户端初始化"""
    assert client.testnet is True
    assert "testnet" in client.base_url


def test_sign(client):
    """测试签名生成"""
    params = {"symbol": "BTCUSDT", "timestamp": 1234567890}
    signature = client._sign(params)
    assert isinstance(signature, str)
    assert len(signature) == 64


@pytest.mark.asyncio
async def test_get_account(client):
    """测试获取账户信息"""
    mock_response = {
        "makerCommission": 15,
        "takerCommission": 15,
        "balances": [
            {"asset": "BTC", "free": "0.5", "locked": "0.0"},
            {"asset": "USDT", "free": "10000.0", "locked": "0.0"}
        ]
    }

    with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        result = await client.get_account()
        assert result == mock_response
        mock_request.assert_called_once_with("GET", "/api/v3/account", signed=True)


@pytest.mark.asyncio
async def test_create_order(client):
    """测试创建订单"""
    mock_response = {
        "orderId": "12345678",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": "0.1",
        "price": "42000.00",
        "status": "NEW"
    }

    with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        result = await client.create_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.1,
            price=42000.0,
            time_in_force="GTC"
        )
        assert result == mock_response
        assert result["orderId"] == "12345678"
