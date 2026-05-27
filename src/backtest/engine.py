from __future__ import annotations


def run_daily_backtest(
    symbol: str,
    bars: list[dict],
    initial_cash: float,
    signals: list[dict],
) -> dict:
    """日频回测主循环。

    bars:    [{"date": "2025-01-02", "close": 100.0}, ...]
    signals: [{"date": "2025-01-02", "action": "BUY", "target_position_ratio": 0.2}, ...]
    """
    cash = initial_cash
    position = 0
    equity_curve: list[float] = []
    trades: list[dict] = []
    signal_by_date = {row["date"]: row for row in signals}

    for bar in bars:
        signal = signal_by_date.get(bar["date"])
        price = bar["close"]

        if signal:
            action = signal.get("action", "HOLD")
            if action == "BUY" and signal.get("target_position_ratio", 0) > 0:
                target_value = initial_cash * signal["target_position_ratio"]
                quantity = int(target_value / price)
                if quantity > 0:
                    cash -= quantity * price
                    position += quantity
                    trades.append({
                        "date": bar["date"],
                        "side": "BUY",
                        "quantity": quantity,
                        "price": price,
                        "notional": quantity * price,
                    })
            elif action == "SELL" and position > 0:
                cash += position * price
                trades.append({
                    "date": bar["date"],
                    "side": "SELL",
                    "quantity": position,
                    "price": price,
                    "notional": position * price,
                })
                position = 0

        nav = cash + position * price
        equity_curve.append(nav)

    return {
        "symbol": symbol,
        "equity_curve": equity_curve,
        "trades": trades,
        "final_nav": equity_curve[-1] if equity_curve else initial_cash,
    }
