from typing import Dict, Any
import random

class PaperBroker:
    def __init__(self, fill_rate: float = 0.9) -> None:
        self.fill_rate = fill_rate
        self._orders: Dict[str, Dict[str, Any]] = {}

    def submit_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """提交订单（模拟）"""
        order_id = order.get("order_id", f"paper-{random.randint(1000, 9999)}")
        self._orders[order_id] = order
        return {
            "broker_order_id": order_id,
            "accepted": True,
            "status": "SUBMITTED",
        }

    def simulate_fill(self, order_id: str) -> Dict[str, Any]:
        """模拟成交"""
        if random.random() < self.fill_rate:
            return {
                "event_type": "FILLED",
                "order_id": order_id,
                "fill_quantity": self._orders.get(order_id, {}).get("quantity", 100),
            }
        return {
            "event_type": "PARTIAL_FILL",
            "order_id": order_id,
            "fill_quantity": random.randint(10, 50),
        }
