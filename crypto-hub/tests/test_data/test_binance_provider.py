import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.data.binance_provider import BinanceProvider


@pytest.fixture
def provider():
    return BinanceProvider(
        api_key="test_api_key",
        api_secret="test_api_secret",
        testnet=True
    )


def test_provider_initialization(provider):
    """测试提供者初始化"""
    assert provider.testnet is True
    assert "testnet" in provider.base_url


def test_sign(provider):
    """测试签名生成"""
    params = {"symbol": "BTCUSDT", "timestamp": 1234567890}
    signature = provider._sign(params)
    assert isinstance(signature, str)
    assert len(signature) == 64  # SHA256 hex length


@pytest.mark.asyncio
async def test_get_server_time(provider):
    """测试获取服务器时间"""
    mock_response = {"serverTime": 1234567890}
    
    with patch.object(provider.client, 'request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = AsyncMock(
            json=lambda: mock_response,
            raise_for_status=lambda: None
        )
        result = await provider.get_server_time()
        assert result == mock_response


@pytest.mark.asyncio
async def test_get_ticker(provider):
    """测试获取实时价格"""
    mock_response = {"symbol": "BTCUSDT", "price": "42000.00"}
    
    with patch.object(provider.client, 'request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = AsyncMock(
            json=lambda: mock_response,
            raise_for_status=lambda: None
        )
        result = await provider.get_ticker("BTCUSDT")
        assert result["symbol"] == "BTCUSDT"
        assert result["price"] == "42000.00"