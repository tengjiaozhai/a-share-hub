import json
import redis.asyncio as redis
from typing import Optional, Dict, Any, List
from datetime import timedelta


class DataCache:
    """数据缓存"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = timedelta(minutes=1)
    
    async def get(self, key: str) -> Optional[Dict]:
        """获取缓存数据"""
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set(self, key: str, value: Dict, ttl: Optional[timedelta] = None):
        """设置缓存数据"""
        if ttl is None:
            ttl = self.default_ttl
        await self.redis.setex(key, ttl, json.dumps(value))
    
    async def delete(self, key: str):
        """删除缓存数据"""
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        return bool(await self.redis.exists(key))
    
    def _make_key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        return f"crypto:{prefix}:{':'.join(str(arg) for arg in args)}"
    
    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """获取缓存的ticker"""
        key = self._make_key("ticker", symbol)
        return await self.get(key)
    
    async def set_ticker(self, symbol: str, data: Dict):
        """设置ticker缓存"""
        key = self._make_key("ticker", symbol)
        await self.set(key, data, ttl=timedelta(seconds=30))
    
    async def get_klines(self, symbol: str, interval: str) -> Optional[List]:
        """获取缓存的K线数据"""
        key = self._make_key("klines", symbol, interval)
        return await self.get(key)
    
    async def set_klines(self, symbol: str, interval: str, data: List):
        """设置K线数据缓存"""
        key = self._make_key("klines", symbol, interval)
        await self.set(key, data, ttl=timedelta(minutes=5))
    
    async def get_order_book(self, symbol: str) -> Optional[Dict]:
        """获取缓存的订单簿"""
        key = self._make_key("orderbook", symbol)
        return await self.get(key)
    
    async def set_order_book(self, symbol: str, data: Dict):
        """设置订单簿缓存"""
        key = self._make_key("orderbook", symbol)
        await self.set(key, data, ttl=timedelta(seconds=10))
    
    async def close(self):
        """关闭Redis连接"""
        await self.redis.close()
