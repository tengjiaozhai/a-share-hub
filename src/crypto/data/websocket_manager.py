import asyncio
import json
import websockets
from typing import Dict, List, Callable, Optional
from datetime import datetime


class WebSocketManager:
    """WebSocket管理器"""

    def __init__(self, testnet: bool = True):
        self.testnet = testnet
        if testnet:
            self.ws_url = "wss://testnet.binance.vision/ws"
        else:
            self.ws_url = "wss://stream.binance.com:9443/ws"

        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.running = False

    async def connect(self, stream: str) -> websockets.WebSocketClientProtocol:
        """连接到WebSocket流"""
        url = f"{self.ws_url}/{stream}"
        ws = await websockets.connect(url)
        self.connections[stream] = ws
        return ws

    async def disconnect(self, stream: str):
        """断开WebSocket连接"""
        if stream in self.connections:
            await self.connections[stream].close()
            del self.connections[stream]

    async def subscribe(self, stream: str, callback: Callable):
        """订阅数据流"""
        if stream not in self.callbacks:
            self.callbacks[stream] = []
        self.callbacks[stream].append(callback)

        if stream not in self.connections:
            await self.connect(stream)

    async def unsubscribe(self, stream: str):
        """取消订阅"""
        if stream in self.callbacks:
            del self.callbacks[stream]
        await self.disconnect(stream)

    async def _handle_message(self, stream: str, message: str):
        """处理消息"""
        data = json.loads(message)
        if stream in self.callbacks:
            for callback in self.callbacks[stream]:
                await callback(data)

    async def _listen(self, stream: str):
        """监听WebSocket消息"""
        ws = self.connections[stream]
        try:
            async for message in ws:
                await self._handle_message(stream, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"WebSocket connection closed for {stream}")
        finally:
            await self.disconnect(stream)

    async def start(self):
        """启动所有WebSocket监听"""
        self.running = True
        tasks = []
        for stream in list(self.connections.keys()):
            task = asyncio.create_task(self._listen(stream))
            tasks.append(task)
        await asyncio.gather(*tasks)

    async def stop(self):
        """停止所有WebSocket连接"""
        self.running = False
        for stream in list(self.connections.keys()):
            await self.unsubscribe(stream)

    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """订阅实时价格"""
        stream = f"{symbol.lower()}@ticker"
        await self.subscribe(stream, callback)

    async def subscribe_kline(self, symbol: str, interval: str, callback: Callable):
        """订阅K线数据"""
        stream = f"{symbol.lower()}@kline_{interval}"
        await self.subscribe(stream, callback)

    async def subscribe_depth(self, symbol: str, callback: Callable):
        """订阅深度数据"""
        stream = f"{symbol.lower()}@depth"
        await self.subscribe(stream, callback)
