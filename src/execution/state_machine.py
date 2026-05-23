from typing import Dict, Any

def apply_broker_event(state: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """应用经纪商事件到订单状态"""
    event_type = event.get("event_type", "")
    
    if event_type == "PARTIAL_FILL":
        return {
            **state,
            "status": "PARTIALLY_FILLED",
            "filled_quantity": state.get("filled_quantity", 0) + event.get("fill_quantity", 0),
        }
    if event_type == "FILLED":
        return {
            **state,
            "status": "FILLED",
            "filled_quantity": state.get("quantity", 0),
        }
    if event_type == "CANCELLED":
        return {**state, "status": "CANCELLED"}
    if event_type == "REJECTED":
        return {**state, "status": "REJECTED", "reject_reason": event.get("reason", "")}
    return state

def create_initial_order_state(order_id: str, symbol: str, quantity: int, side: str) -> Dict[str, Any]:
    """创建初始订单状态"""
    return {
        "order_id": order_id,
        "symbol": symbol,
        "quantity": quantity,
        "side": side,
        "status": "PENDING",
        "filled_quantity": 0,
    }
