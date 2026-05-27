from __future__ import annotations


def run_long_horizon_evaluation(store, window: str, mode: str) -> dict:
    """运行长期 shadow 评估，返回统一指标字典。

    window: "1m" | "3m" | "1y"
    mode:   "shadow" | "live"
    """
    decision_runs = store.list_decision_runs()
    reconciliation = store.get_reconciliation_status()

    metrics = {
        "total_return": 0.0,
        "max_drawdown": 0.0,
        "turnover": 0.0,
        "decision_count": len(decision_runs),
        "fill_rate": 1.0,
        "unreconciled_order_count": reconciliation.get("open_orders", 0),
    }

    return {"window": window, "mode": mode, "metrics": metrics}
