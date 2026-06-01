import pytest
from src.crypto.execution.binance_client import BinanceClient

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