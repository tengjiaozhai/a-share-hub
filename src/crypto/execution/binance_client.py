import httpx
import hashlib
import hmac
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode
from ..core.enums import OrderSide, OrderType


class BinanceClient:
    """币安API客户端"""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        if testnet:
            self.base_url = "https://testnet.binance.vision"
        else:
            self.base_url = "https://api.binance.com"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-MBX-APIKEY": api_key}
        )

    def _sign(self, params: Dict) -> str:
        """生成签名"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, path: str, params: Dict = None, signed: bool = False) -> Dict:
        """发送请求"""
        if params is None:
            params = {}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign(params)

        response = await self.client.request(method, path, params=params)
        response.raise_for_status()
        return response.json()

    async def get_account(self) -> Dict:
        """获取账户信息"""
        return await self._request("GET", "/api/v3/account", signed=True)

    async def get_balance(self, asset: Optional[str] = None) -> List[Dict]:
        """获取余额"""
        account = await self.get_account()
        balances = account.get("balances", [])

        if asset:
            balances = [b for b in balances if b["asset"] == asset]

        return balances

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: Optional[str] = None
    ) -> Dict:
        """创建订单"""
        params = {
            "symbol": symbol,
            "side": side.value,
            "type": order_type.value,
            "quantity": quantity
        }

        if price is not None:
            params["price"] = price

        if time_in_force is not None:
            params["timeInForce"] = time_in_force

        return await self._request("POST", "/api/v3/order", params, signed=True)

    async def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """取消订单"""
        return await self._request("DELETE", "/api/v3/order", {
            "symbol": symbol,
            "orderId": order_id
        }, signed=True)

    async def get_order(self, symbol: str, order_id: str) -> Dict:
        """查询订单"""
        return await self._request("GET", "/api/v3/order", {
            "symbol": symbol,
            "orderId": order_id
        }, signed=True)

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取未成交订单"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._request("GET", "/api/v3/openOrders", params, signed=True)

    async def get_my_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """获取成交历史"""
        return await self._request("GET", "/api/v3/myTrades", {
            "symbol": symbol,
            "limit": limit
        }, signed=True)

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
