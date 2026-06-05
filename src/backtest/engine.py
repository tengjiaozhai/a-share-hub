from __future__ import annotations

from src.core.market_rules import calculate_lot_quantity


def run_daily_backtest(
    symbol: str,
    bars: list[dict],
    initial_cash: float,
    signals: list[dict],
    lot_size: int = 100,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict:
    cash = float(initial_cash)
    position = 0
    avg_cost = 0.0
    equity_curve: list[float] = []
    trades: list[dict] = []
    signal_by_date = {row["date"]: row for row in signals}

    for bar in bars:
        date = bar["date"]
        price = float(bar["close"])
        signal = signal_by_date.get(date, {"action": "HOLD"})
        action = signal.get("action", "HOLD")

        if action == "BUY" and signal.get("target_position_ratio", 0) > 0:
            target_value = initial_cash * float(signal["target_position_ratio"])
            current_value = position * price
            delta_value = max(target_value - current_value, 0.0)
            quantity = calculate_lot_quantity(delta_value, price, lot_size)
            if quantity > 0:
                fill_price = round(price * (1 + slippage_bps / 10_000), 4)
                notional = quantity * fill_price
                fee = round(notional * fee_bps / 10_000, 2)
                if cash >= notional + fee:
                    total_cost = position * avg_cost + notional
                    position += quantity
                    avg_cost = total_cost / position
                    cash -= notional + fee
                    trades.append({
                        "date": date,
                        "side": "BUY",
                        "quantity": quantity,
                        "price": fill_price,
                        "notional": round(notional, 2),
                        "fee": fee,
                    })
        elif action == "SELL" and position > 0:
            fill_price = round(price * (1 - slippage_bps / 10_000), 4)
            quantity = position
            notional = quantity * fill_price
            fee = round(notional * fee_bps / 10_000, 2)
            cash += notional - fee
            trades.append({
                "date": date,
                "side": "SELL",
                "quantity": quantity,
                "price": fill_price,
                "notional": round(notional, 2),
                "fee": fee,
            })
            position = 0
            avg_cost = 0.0

        equity_curve.append(round(cash + position * price, 2))

    return {
        "symbol": symbol,
        "equity_curve": equity_curve,
        "trades": trades,
        "final_nav": equity_curve[-1] if equity_curve else initial_cash,
    }
