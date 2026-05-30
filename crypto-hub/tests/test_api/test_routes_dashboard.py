import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_get_status():
    """测试获取系统状态"""
    response = client.get("/api/dashboard/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "api_connected" in data["data"]

def test_get_balance():
    """测试获取账户余额"""
    response = client.get("/api/dashboard/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "usdt_balance" in data["data"]

def test_get_positions():
    """测试获取持仓"""
    response = client.get("/api/dashboard/positions")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_get_orders():
    """测试获取订单"""
    response = client.get("/api/dashboard/orders")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_get_signals():
    """测试获取信号"""
    response = client.get("/api/dashboard/signals")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_get_indicators():
    """测试获取技术指标"""
    response = client.get("/api/dashboard/indicators/BTCUSDT")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["symbol"] == "BTCUSDT"