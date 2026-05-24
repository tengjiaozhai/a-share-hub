from typing import Dict, Any

def local_gate(
    trader_connected: bool,
    available_cash: float,
    requested_value: float,
    requested_quantity: int = 0,
    available_sell_quantity: int = 0,
    action: str = "BUY",
) -> Dict[str, Any]:
    """本地风险检查"""
    if not trader_connected:
        return {"approved": False, "reason": "trader disconnected"}
    if action == "BUY" and requested_value > available_cash:
        return {"approved": False, "reason": "insufficient local cash"}
    if action == "SELL" and requested_quantity > available_sell_quantity:
        return {"approved": False, "reason": "insufficient available sell quantity"}
    return {"approved": True, "reason": "approved"}
