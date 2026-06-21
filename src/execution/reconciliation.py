from typing import Dict, Any

def detect_unreconciled_state(plan: Dict[str, Any], broker: Dict[str, Any]) -> bool:
    """检测未对账状态（包括状态漂移）"""
    # 检查数量漂移
    quantity_drift = plan.get("filled_quantity", 0) != broker.get("filled_quantity", 0)

    # 检查状态漂移
    status_drift = plan.get("status") != broker.get("status")

    # 任何漂移都返回True
    return quantity_drift or status_drift

def reconcile_positions(system_positions: Dict[str, int], broker_positions: Dict[str, int]) -> Dict[str, Any]:
    """对账持仓"""
    discrepancies = {}
    all_symbols = set(list(system_positions.keys()) + list(broker_positions.keys()))

    for symbol in all_symbols:
        system_qty = system_positions.get(symbol, 0)
        broker_qty = broker_positions.get(symbol, 0)
        if system_qty != broker_qty:
            discrepancies[symbol] = {
                "system": system_qty,
                "broker": broker_qty,
                "difference": system_qty - broker_qty,
            }

    return {
        "reconciled": len(discrepancies) == 0,
        "discrepancies": discrepancies,
    }
