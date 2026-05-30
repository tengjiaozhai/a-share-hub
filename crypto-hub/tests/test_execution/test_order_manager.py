import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.execution.order_manager import OrderManager, OrderRequest
from src.core.enums import OrderSide, OrderType
from src.risk.risk_manager import RiskManager


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.create_order.return_value = {
        "orderId": "12345678",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": "0.1",
        "price": "42000.00",
        "status": "NEW"
    }
    return client


@pytest.fixture
def mock_risk_manager():
    risk_manager = AsyncMock()
    risk_manager.check_order.return_value = {"passed": True, "reason": "approved"}
    return risk_manager


@pytest.fixture
def order_manager(mock_client, mock_risk_manager):
    return OrderManager(mock_client, mock_risk_manager)


@pytest.mark.asyncio
async def test_place_order(order_manager, mock_client, mock_risk_manager):
    """测试下单"""
    order_request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.1,
        price=42000.0
    )
    
    result = await order_manager.place_order(order_request)
    
    assert result["orderId"] == "12345678"
    assert result["status"] == "NEW"
    mock_risk_manager.check_order.assert_called_once_with(order_request)
    mock_client.create_order.assert_called_once()


@pytest.mark.asyncio
async def test_place_order_risk_check_failed(order_manager, mock_risk_manager):
    """测试风控检查失败"""
    mock_risk_manager.check_order.return_value = {"passed": False, "reason": "风控检查失败"}
    
    order_request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.1,
        price=42000.0
    )
    
    with pytest.raises(Exception) as exc_info:
        await order_manager.place_order(order_request)
    
    assert "风控检查失败" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancel_order(order_manager, mock_client):
    """测试取消订单"""
    mock_client.cancel_order.return_value = {"orderId": "12345678", "status": "CANCELED"}
    
    result = await order_manager.cancel_order("BTCUSDT", "12345678")
    
    assert result["status"] == "CANCELED"
    mock_client.cancel_order.assert_called_once_with("BTCUSDT", "12345678")


@pytest.mark.asyncio
async def test_get_open_orders(order_manager, mock_client):
    """测试获取未成交订单"""
    mock_orders = [
        {"orderId": "123", "symbol": "BTCUSDT", "status": "NEW"},
        {"orderId": "456", "symbol": "ETHUSDT", "status": "NEW"}
    ]
    mock_client.get_open_orders.return_value = mock_orders
    
    result = await order_manager.get_open_orders("BTCUSDT")
    
    assert len(result) == 2
    mock_client.get_open_orders.assert_called_once_with("BTCUSDT")


@pytest.mark.asyncio
async def test_place_order_with_stop_loss(order_manager, mock_client, mock_risk_manager):
    """测试带止损的下单"""
    order_request = OrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=0.1,
        price=42000.0,
        stop_loss=41000.0
    )
    
    result = await order_manager.place_order(order_request)
    
    assert result["orderId"] == "12345678"
    # 验证止损单也被创建
    assert mock_client.create_order.call_count == 2


@pytest.mark.asyncio
async def test_cancel_all_orders(order_manager, mock_client):
    """测试取消所有订单"""
    mock_orders = [
        {"orderId": "123", "symbol": "BTCUSDT", "status": "NEW"},
        {"orderId": "456", "symbol": "BTCUSDT", "status": "NEW"}
    ]
    mock_client.get_open_orders.return_value = mock_orders
    mock_client.cancel_order.return_value = {"status": "CANCELED"}
    
    results = await order_manager.cancel_all_orders("BTCUSDT")
    
    assert len(results) == 2
    assert mock_client.cancel_order.call_count == 2