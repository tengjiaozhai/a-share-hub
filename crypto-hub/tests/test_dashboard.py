import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_dashboard_page():
    """测试仪表盘页面"""
    response = client.get("/api/dashboard/dashboard")
    assert response.status_code == 200


def test_api_endpoints():
    """测试所有API端点"""
    # 测试系统状态
    response = client.get("/api/dashboard/status")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 测试账户余额
    response = client.get("/api/dashboard/balance")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 测试持仓
    response = client.get("/api/dashboard/positions")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 测试订单
    response = client.get("/api/dashboard/orders")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 测试信号
    response = client.get("/api/dashboard/signals")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # 测试技术指标
    response = client.get("/api/dashboard/indicators/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["symbol"] == "BTCUSDT"


def test_static_files():
    """测试静态文件"""
    response = client.get("/static/css/style.css")
    assert response.status_code == 200

    response = client.get("/static/js/dashboard.js")
    assert response.status_code == 200
