from typing import Dict, Any

def build_execution_plan(target_position: Dict[str, Any], risk_gate: Dict[str, Any]) -> Dict[str, Any]:
    """构建执行计划"""
    return {
        "symbol": target_position["symbol"],
        "ready": risk_gate["approved"],
        "reason": risk_gate["reason"],
        "target_value": target_position["target_value"],
        "action": target_position["action"],
    }
