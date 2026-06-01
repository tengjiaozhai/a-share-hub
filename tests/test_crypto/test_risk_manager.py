import pytest
from unittest.mock import AsyncMock, MagicMock
from src.crypto.risk.risk_manager import RiskManager
from src.crypto.core.enums import OrderSide, OrderType

@pytest.fixture
def config():
    return {
        "max_position_ratio": 0.1,
        "max_daily_loss": 0.05,
        "max_volatility": 0.1,
        "min_liquidity": 1000000,
        "stop_loss_ratio": 0.02
    }

@pytest.fixture
def risk_manager(config):
    return RiskManager(config)

def test_risk_manager_initialization(risk_manager, config):
    """测试风险管理器初始化"""
    assert risk_manager.max_position_ratio == config["max_position_ratio"]
    assert risk_manager.max_daily_loss == config["max_daily_loss"]
    assert risk_manager.max_volatility == config["max_volatility"]
    assert risk_manager.min_liquidity == config["min_liquidity"]
    assert risk_manager.stop_loss_ratio == config["stop_loss_ratio"]

def test_risk_manager_default_config():
    """测试默认配置"""
    risk_manager = RiskManager({})
    assert risk_manager.max_position_ratio == 0.1
    assert risk_manager.max_daily_loss == 0.05
    assert risk_manager.max_volatility == 0.1
    assert risk_manager.min_liquidity == 1000000
    assert risk_manager.stop_loss_ratio == 0.02

@pytest.mark.asyncio
async def test_check_order_pass(risk_manager):
    """测试订单检查通过"""
    order_request = MagicMock()
    order_request.symbol = "BTCUSDT"
    order_request.quantity = 0.001
    
    result = await risk_manager.check_order(order_request)
    assert result["passed"] is True
    assert result["reason"] == "approved"

@pytest.mark.asyncio
async def test_update_daily_pnl(risk_manager):
    """测试更新每日盈亏"""
    await risk_manager.update_daily_pnl(100.0)
    assert risk_manager.daily_pnl == 100.0
    assert risk_manager.daily_trades == 1

def test_get_risk_metrics(risk_manager):
    """测试获取风险指标"""
    metrics = risk_manager.get_risk_metrics()
    assert "daily_pnl" in metrics
    assert "daily_trades" in metrics
    assert "max_position_ratio" in metrics
    assert "max_daily_loss" in metrics
    assert "max_volatility" in metrics
    assert "min_liquidity" in metrics