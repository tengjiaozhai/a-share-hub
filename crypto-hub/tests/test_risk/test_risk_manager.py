import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.risk.risk_manager import RiskManager
from src.core.enums import OrderSide


@pytest.fixture
def risk_manager():
    config = {
        "max_position_ratio": 0.1,
        "max_daily_loss": 0.05,
        "max_volatility": 0.1,
        "min_liquidity": 1000000,
        "stop_loss_ratio": 0.02
    }
    return RiskManager(config)


def test_risk_manager_initialization(risk_manager):
    """测试风险管理器初始化"""
    assert risk_manager.max_position_ratio == 0.1
    assert risk_manager.max_daily_loss == 0.05
    assert risk_manager.daily_pnl == 0.0


@pytest.mark.asyncio
async def test_check_order_pass(risk_manager):
    """测试订单检查通过"""
    order_request = AsyncMock()
    order_request.symbol = "BTCUSDT"
    order_request.quantity = 0.1

    # Mock所有检查方法
    with patch.object(risk_manager, '_check_daily_loss', return_value=True):
        with patch.object(risk_manager, '_check_position_limit', return_value=True):
            with patch.object(risk_manager, '_check_volatility', return_value=0.05):
                with patch.object(risk_manager, '_check_liquidity', return_value=1000000):
                    result = await risk_manager.check_order(order_request)

                    assert result["passed"] is True
                    assert result["reason"] == "approved"


@pytest.mark.asyncio
async def test_check_order_daily_loss_exceeded(risk_manager):
    """测试每日亏损超限"""
    order_request = AsyncMock()
    order_request.symbol = "BTCUSDT"
    order_request.quantity = 0.1

    # 设置每日亏损超限
    risk_manager.daily_pnl = -0.06

    result = await risk_manager.check_order(order_request)

    assert result["passed"] is False
    assert "每日亏损超限" in result["reason"]


@pytest.mark.asyncio
async def test_check_order_volatility_high(risk_manager):
    """测试波动率过高"""
    order_request = AsyncMock()
    order_request.symbol = "BTCUSDT"
    order_request.quantity = 0.1

    with patch.object(risk_manager, '_check_daily_loss', return_value=True):
        with patch.object(risk_manager, '_check_position_limit', return_value=True):
            with patch.object(risk_manager, '_check_volatility', return_value=0.15):
                result = await risk_manager.check_order(order_request)

                assert result["passed"] is False
                assert "波动率过高" in result["reason"]


@pytest.mark.asyncio
async def test_update_daily_pnl(risk_manager):
    """测试更新每日盈亏"""
    await risk_manager.update_daily_pnl(100.0)
    assert risk_manager.daily_pnl == 100.0
    assert risk_manager.daily_trades == 1

    await risk_manager.update_daily_pnl(-50.0)
    assert risk_manager.daily_pnl == 50.0
    assert risk_manager.daily_trades == 2


def test_get_risk_metrics(risk_manager):
    """测试获取风险指标"""
    metrics = risk_manager.get_risk_metrics()

    assert "daily_pnl" in metrics
    assert "daily_trades" in metrics
    assert "max_position_ratio" in metrics
    assert "max_daily_loss" in metrics
