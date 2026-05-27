from __future__ import annotations


def calculate_metrics(equity_curve: list[float], trades: list[dict]) -> dict:
    """计算回测指标：total_return, max_drawdown, turnover, win_rate。"""
    if not equity_curve:
        return {"total_return": 0.0, "max_drawdown": 0.0, "turnover": 0.0, "win_rate": 0.0}

    start = equity_curve[0]
    end = equity_curve[-1]

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (value - peak) / peak if peak != 0 else 0.0
        if dd < max_dd:
            max_dd = dd

    # Turnover = total traded notional / initial NAV
    total_notional = sum(t.get("notional", 0) for t in trades)
    turnover = total_notional / start if start != 0 else 0.0

    # Win rate (simplified: no BUY/SELL pairing)
    win_rate = 0.0

    return {
        "total_return": round((end - start) / start, 6) if start != 0 else 0.0,
        "max_drawdown": round(max_dd, 6),
        "turnover": round(turnover, 4),
        "win_rate": win_rate,
    }
