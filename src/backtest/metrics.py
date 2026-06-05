from __future__ import annotations


def calculate_metrics(equity_curve: list[float], trades: list[dict]) -> dict:
    if not equity_curve:
        return {"total_return": 0.0, "max_drawdown": 0.0, "turnover": 0.0, "win_rate": 0.0}

    start = equity_curve[0]
    end = equity_curve[-1]
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        dd = (value - peak) / peak if peak != 0 else 0.0
        max_dd = min(max_dd, dd)

    total_notional = sum(float(t.get("notional", 0)) for t in trades)
    paired_results = _paired_trade_results(trades)
    win_rate = (
        sum(1 for value in paired_results if value > 0) / len(paired_results)
        if paired_results else 0.0
    )

    return {
        "total_return": round((end - start) / start, 6) if start != 0 else 0.0,
        "max_drawdown": round(max_dd, 6),
        "turnover": round(total_notional / start, 4) if start != 0 else 0.0,
        "win_rate": round(win_rate, 4),
    }


def _paired_trade_results(trades: list[dict]) -> list[float]:
    open_buy: dict | None = None
    results: list[float] = []
    for trade in trades:
        if trade.get("side") == "BUY":
            open_buy = trade
        elif trade.get("side") == "SELL" and open_buy is not None:
            buy_price = float(open_buy["price"])
            sell_price = float(trade["price"])
            quantity = min(int(open_buy["quantity"]), int(trade["quantity"]))
            results.append((sell_price - buy_price) * quantity)
            open_buy = None
    return results
