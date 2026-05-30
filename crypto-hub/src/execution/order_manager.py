from typing import Dict, List, Optional
from datetime import datetime
from ..core.enums import OrderSide, OrderType, OrderStatus
from .binance_client import BinanceClient
from ..risk.risk_manager import RiskManager


class OrderRequest:
    """订单请求"""
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None
    ):
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.stop_loss = stop_loss


class OrderManager:
    """订单管理器"""
    
    def __init__(self, client: BinanceClient, risk_manager: RiskManager):
        self.client = client
        self.risk_manager = risk_manager
    
    async def place_order(self, order_request: OrderRequest) -> Dict:
        """下单"""
        # 1. 风控检查
        risk_check = await self.risk_manager.check_order(order_request)
        if not risk_check["passed"]:
            raise Exception(f"风控检查失败: {risk_check['reason']}")
        
        # 2. 创建订单
        order = await self.client.create_order(
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            quantity=order_request.quantity,
            price=order_request.price,
            time_in_force="GTC" if order_request.order_type == OrderType.LIMIT else None
        )
        
        # 3. 设置止损单（如果需要）
        if order_request.stop_loss and order_request.side == OrderSide.BUY:
            await self._place_stop_loss(
                symbol=order_request.symbol,
                quantity=order_request.quantity,
                stop_price=order_request.stop_loss
            )
        
        return order
    
    async def _place_stop_loss(self, symbol: str, quantity: float, stop_price: float) -> Dict:
        """设置止损单"""
        return await self.client.create_order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LOSS,
            quantity=quantity,
            price=stop_price
        )
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        return await self.client.cancel_order(symbol, order_id)
    
    async def get_order(self, symbol: str, order_id: str) -> Dict:
        """查询订单"""
        return await self.client.get_order(symbol, order_id)
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取未成交订单"""
        return await self.client.get_open_orders(symbol)
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """取消所有订单"""
        open_orders = await self.get_open_orders(symbol)
        results = []
        
        for order in open_orders:
            result = await self.cancel_order(order["symbol"], order["orderId"])
            results.append(result)
        
        return results