import pytest
from unittest.mock import AsyncMock, MagicMock
from src.crypto.execution.order_manager import OrderManager, OrderRequest
from src.crypto.execution.binance_client import BinanceClient
from src.crypto.risk.risk_manager import RiskManager
from src.crypto.core.enums import OrderSide, OrderType

@pytest.fixture
def mock_client():
    client = AsyncMock(spec=BinanceClient)
    return client

@pytest.fixture
def mock_risk_manager():
    risk_manager = AsyncMock(spec=RiskManager)
    risk_manager.check_order.return_value = {"passed": True, "reason": "approved"}
    return risk_manager

@pytest.fixture
def order_manager(mock_client, mock_risk_manager):
    return OrderManager(mock_client, mock_risk_manager)

def test_order_manager_initialization(order_manager, mock_client, mock_risk_manager):
    """测试订单管理器初始化"""
    assert order_manager.client == mock_client
    assert order_manager.risk_manager == mock_risk_manager

@pytest.mark.asyncio
async def test_place_order(order_manager, mock_client, mock_risk_manager):
    """测试下单"""
    order_request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001
    )
    
    mock_client.create_order.return_value = {"orderId": 12345, "status": "FILLED"}
    
    result = await order_manager.place_order(order_request)
    
    mock_risk_manager.check_order.assert_called_once_with(order_request)
    mock_client.create_order.assert_called_once()
    assert result["orderId"] == 12345