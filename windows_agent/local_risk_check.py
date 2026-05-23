from typing import Dict, Any

def local_gate(trader_connected: bool, available_cash: float, requested_value: float) -> Dict[str, Any]:
    """本地风险检查"""
    if not trader_connected:
        return {"approved": False, "reason": "trader disconnected"}
    if requested_value > available_cash:
        return {"approved": False, "reason": "insufficient local cash"}
    return {"approved": True, "reason": "approved"}
