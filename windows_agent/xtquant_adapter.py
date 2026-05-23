from typing import Dict, Any

class XtQuantAdapter:
    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> bool:
        """连接到QMT"""
        self.connected = True
        return True

    def submit_order(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """提交订单"""
        return {
            "broker_order_id": f"qmt-{plan.get('plan_id', 'unknown')}",
            "accepted": self.connected,
            "status": "SUBMITTED" if self.connected else "REJECTED",
        }

    def disconnect(self) -> None:
        """断开连接"""
        self.connected = False
