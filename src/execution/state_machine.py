from typing import Dict, Any, Set

def apply_broker_event(state: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """应用经纪商事件到订单状态（幂等）"""
    event_type = event.get("event_type", "")
    event_id = event.get("event_id")
    
    # 幂等性检查：如果事件有ID且已处理过，则忽略
    processed_events: Set[str] = state.get("processed_events", set())
    if event_id and event_id in processed_events:
        return state
    
    # 复制状态以避免修改原始状态
    new_state = {**state}
    
    # 将processed_events转换为列表以便序列化（如果原来是集合）
    if isinstance(new_state.get("processed_events"), set):
        new_state["processed_events"] = list(new_state["processed_events"])
    
    if event_type == "PARTIAL_FILL":
        # 计算新的filled_quantity，但不能超过订单数量
        current_filled = new_state.get("filled_quantity", 0)
        fill_quantity = event.get("fill_quantity", 0)
        order_quantity = new_state.get("quantity", 0)
        
        # 防止超过订单数量
        new_filled = min(current_filled + fill_quantity, order_quantity)
        
        # 确定新状态
        if new_filled >= order_quantity:
            new_status = "FILLED"
        else:
            new_status = "PARTIALLY_FILLED"
        
        new_state.update({
            "status": new_status,
            "filled_quantity": new_filled,
        })
    elif event_type == "FILLED":
        new_state.update({
            "status": "FILLED",
            "filled_quantity": new_state.get("quantity", 0),
        })
    elif event_type == "CANCELLED":
        new_state["status"] = "CANCELLED"
    elif event_type == "REJECTED":
        new_state.update({
            "status": "REJECTED",
            "reject_reason": event.get("reason", ""),
        })
    
    # 记录已处理的事件ID
    if event_id:
        if "processed_events" not in new_state:
            new_state["processed_events"] = []
        new_state["processed_events"].append(event_id)
    
    return new_state

def create_initial_order_state(order_id: str, symbol: str, quantity: int, side: str) -> Dict[str, Any]:
    """创建初始订单状态"""
    return {
        "order_id": order_id,
        "symbol": symbol,
        "quantity": quantity,
        "side": side,
        "status": "PENDING",
        "filled_quantity": 0,
        "processed_events": [],  # 跟踪已处理的事件ID
    }
