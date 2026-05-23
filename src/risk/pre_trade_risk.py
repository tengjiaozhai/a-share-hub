from typing import Dict, Any

def evaluate_risk_gate(
    symbol: str,
    action: str,
    kill_switch: bool,
    available_cash: float,
    requested_value: float,
) -> Dict[str, Any]:
    """评估交易前风险"""
    if kill_switch:
        return {"approved": False, "reason": "kill switch enabled"}
    if action == "BUY" and requested_value > available_cash:
        return {"approved": False, "reason": "insufficient cash"}
    if action == "BUY" and requested_value <= 0:
        return {"approved": False, "reason": "invalid request amount"}
    return {"approved": True, "reason": "approved"}
