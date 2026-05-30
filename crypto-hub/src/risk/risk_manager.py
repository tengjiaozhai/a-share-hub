from typing import Dict, Any


class RiskManager:
    """风险管理器"""
    
    def __init__(self, max_position_size: float = 0.1, max_loss_percentage: float = 0.05):
        self.max_position_size = max_position_size
        self.max_loss_percentage = max_loss_percentage
    
    async def check_order(self, order_request: Any) -> Dict:
        """
        检查订单是否符合风控规则
        
        Args:
            order_request: 订单请求对象
            
        Returns:
            Dict: 包含 passed 和 reason 的字典
        """
        # 基本风控检查
        if order_request.quantity <= 0:
            return {"passed": False, "reason": "订单数量必须大于0"}
        
        # 检查仓位大小
        if order_request.quantity > self.max_position_size:
            return {"passed": False, "reason": f"订单数量超过最大仓位限制: {self.max_position_size}"}
        
        # 所有检查通过
        return {"passed": True, "reason": "approved"}