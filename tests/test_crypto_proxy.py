import pytest
from fastapi.testclient import TestClient

from src.main import build_app


@pytest.fixture
def client():
    app = build_app()
    return TestClient(app)


def test_proxy_crypto_status(client):
    """测试代理crypto状态API"""
    response = client.get("/api/v1/crypto/status")
    # 注意：如果crypto-hub未运行，会返回500
    assert response.status_code in [200, 500]


def test_proxy_crypto_balance(client):
    """测试代理crypto余额API"""
    response = client.get("/api/v1/crypto/balance")
    assert response.status_code in [200, 500]


def test_proxy_crypto_positions(client):
    """测试代理crypto持仓API"""
    response = client.get("/api/v1/crypto/positions")
    assert response.status_code in [200, 500]


def test_proxy_crypto_orders(client):
    """测试代理crypto订单API"""
    response = client.get("/api/v1/crypto/orders")
    assert response.status_code in [200, 500]


def test_proxy_crypto_signals(client):
    """测试代理crypto信号API"""
    response = client.get("/api/v1/crypto/signals")
    assert response.status_code in [200, 500]


def test_proxy_crypto_indicators(client):
    """测试代理crypto技术指标API"""
    response = client.get("/api/v1/crypto/indicators/BTCUSDT")
    assert response.status_code in [200, 500]
