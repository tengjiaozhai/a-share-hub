import httpx
import hashlib
import hmac
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode


class BinanceProvider:
    """币安数据提供者"""
    
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
    
    async def get_server_time(self) -> Dict:
        """获取服务器时间"""
        return await self._request("GET", "/api/v3/time")
    
    async def get_exchange_info(self) -> Dict:
        """获取交易规则"""
        return await self._request("GET", "/api/v3/exchangeInfo")
    
    async def get_ticker(self, symbol: str) -> Dict:
        """获取实时价格"""
        return await self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 1000) -> List:
        """获取K线数据"""
        return await self._request("GET", "/api/v3/klines", {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        """获取订单簿"""
        return await self._request("GET", "/api/v3/depth", {
            "symbol": symbol,
            "limit": limit
        })
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()