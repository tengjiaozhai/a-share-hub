from typing import Dict
from datetime import datetime


class RiskManager:
    """风险管理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.max_position_ratio = config.get("max_position_ratio", 0.1)
        self.max_daily_loss = config.get("max_daily_loss", 0.05)
        self.max_volatility = config.get("max_volatility", 0.1)
        self.min_liquidity = config.get("min_liquidity", 1000000)
        self.stop_loss_ratio = config.get("stop_loss_ratio", 0.02)

        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset = datetime.now()

    async def check_order(self, order_request) -> Dict:
        """检查订单风险"""
        # 1. 检查每日亏损
        if not await self._check_daily_loss():
            return {"passed": False, "reason": "每日亏损超限"}

        # 2. 检查持仓限制
        if not await self._check_position_limit(order_request.symbol, order_request.quantity):
            return {"passed": False, "reason": "持仓比例超限"}

        # 3. 检查波动率
        volatility = await self._check_volatility(order_request.symbol)
        if volatility > self.max_volatility:
            return {"passed": False, "reason": f"波动率过高: {volatility:.2%}"}

        # 4. 检查流动性
        liquidity = await self._check_liquidity(order_request.symbol)
        if liquidity < self.min_liquidity:
            return {"passed": False, "reason": f"流动性不足: ${liquidity:,.0f}"}

        return {"passed": True, "reason": "approved"}

    async def _check_daily_loss(self) -> bool:
        """检查每日亏损"""
        # 重置每日计数器
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.last_reset = now

        return abs(self.daily_pnl) < self.max_daily_loss

    async def _check_position_limit(self, symbol: str, quantity: float) -> bool:
        """检查持仓限制"""
        # 这里需要查询实际持仓，暂时返回True
        # 实际实现需要查询数据库或API
        return True

    async def _check_volatility(self, symbol: str) -> float:
        """检查波动率"""
        # 这里需要查询历史数据计算波动率
        # 实际实现需要调用数据提供者
        return 0.05  # 临时返回

    async def _check_liquidity(self, symbol: str) -> float:
        """检查流动性"""
        # 这里需要查询24小时交易量
        # 实际实现需要调用数据提供者
        return 1000000  # 临时返回

    async def update_daily_pnl(self, pnl: float):
        """更新每日盈亏"""
        self.daily_pnl += pnl
        self.daily_trades += 1

    def get_risk_metrics(self) -> Dict:
        """获取风险指标"""
        return {
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "max_position_ratio": self.max_position_ratio,
            "max_daily_loss": self.max_daily_loss,
            "max_volatility": self.max_volatility,
            "min_liquidity": self.min_liquidity
        }
