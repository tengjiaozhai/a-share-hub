import pytest
from src.crypto.data.binance_provider import BinanceProvider

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
    assert len(signature) == 64