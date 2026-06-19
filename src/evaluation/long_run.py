from __future__ import annotations

from datetime import datetime, timedelta

from src.storage.models import SYSTEM_USER_ID

_WINDOW_DAYS = {"1m": 31, "3m": 93, "1y": 366}


def run_long_horizon_evaluation(store, window: str, mode: str, user_id: str = SYSTEM_USER_ID) -> dict:
    if window not in _WINDOW_DAYS:
        return {"status": "error", "window": window, "mode": mode, "reason": "unsupported window"}

    since = datetime.utcnow() - timedelta(days=_WINDOW_DAYS[window])
    snapshots = store.list_account_snapshots(user_id=user_id, since=since)
    decision_runs = store.list_decision_runs(user_id=user_id)
    orders = store.list_execution_orders(user_id=user_id)
    reconciliation = store.get_reconciliation_status(user_id=user_id)

    navs = [float(row["nav"]) for row in snapshots]
    total_return = _total_return(navs)
    max_drawdown = _max_drawdown(navs)
    fill_rate = _fill_rate(orders)

    metrics = {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "turnover": 0.0,
        "decision_count": len(decision_runs),
        "fill_rate": fill_rate,
        "unreconciled_order_count": reconciliation.get("open_orders", 0),
        "snapshot_count": len(snapshots),
    }
    return {"status": "ok", "window": window, "mode": mode, "metrics": metrics}


def _total_return(navs: list[float]) -> float:
    if len(navs) < 2 or navs[0] == 0:
        return 0.0
    return round((navs[-1] - navs[0]) / navs[0], 6)


def _max_drawdown(navs: list[float]) -> float:
    if not navs:
        return 0.0
    peak = navs[0]
    max_dd = 0.0
    for nav in navs:
        peak = max(peak, nav)
        drawdown = (nav - peak) / peak if peak else 0.0
        max_dd = min(max_dd, drawdown)
    return round(max_dd, 6)


def _fill_rate(orders: list[dict]) -> float:
    if not orders:
        return 0.0
    filled = sum(1 for order in orders if order.get("status") == "FILLED")
    return round(filled / len(orders), 4)
